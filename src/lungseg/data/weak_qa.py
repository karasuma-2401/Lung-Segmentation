"""CT+all individual axial rectangles and native coronal/sagittal bbox envelope."""
import csv,json
from pathlib import Path
import nibabel as nib
import numpy as np
from lungseg.data.msd_acquire import file_sha256
from lungseg.data.msd_qa import read_canonical_planes
from lungseg.runs import utc_now,write_json


def generate(config,identity):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    report=json.loads((Path(config.output_dir)/'conversion_report.json').read_text())
    manifest=Path(config.output_dir)/'manifest_weak.csv'
    if report['manifest_sha256']!=file_sha256(manifest) or report['config_sha256']!=config.sha256 or report['implementation']!=identity:
        raise ValueError('Stale manifest/config/implementation; use explicit versioned reconversion')
    rows=list(csv.DictReader(manifest.open(encoding='utf-8',newline='')));records=[]
    for row in rows:
        if row['conversion_status']!='converted':continue
        root=Path(config.converted_root)
        for field,hashfield in [('image_path','image_sha256'),('bbox_path','bbox_sha256'),('boxes_path','boxes_sha256'),('coverage_path','coverage_sha256')]:
            if file_sha256(root/row[field])!=row[hashfield]:raise ValueError('QA input changed after inventory')
        image=nib.load(root/row['image_path'],keep_file_open=True);bbox=nib.load(root/row['bbox_path'])
        if image.shape!=bbox.shape or not np.allclose(image.affine,bbox.affine,atol=config.affine_atol_mm,rtol=0):raise ValueError('QA geometry mismatch')
        boxes=json.loads((root/row['boxes_path']).read_text())['records']
        counts={k:sum(b['slice_index']==k for b in boxes) for k in {b['slice_index'] for b in boxes}}
        k=max(counts,key=lambda i:(counts[i],sum((b['index_bounds_half_open'][2]-b['index_bounds_half_open'][0])*(b['index_bounds_half_open'][3]-b['index_bounds_half_open'][1]) for b in boxes if b['slice_index']==i)))
        transform=nib.orientations.ornt_transform(nib.orientations.io_orientation(image.affine),nib.orientations.axcodes2ornt(('R','A','S')))
        label=nib.orientations.apply_orientation(np.asarray(bbox.dataobj,dtype=np.uint8),transform)
        slices=[int(np.argmax(label.sum(axis=tuple(j for j in range(3) if j!=axis)))) for axis in range(3)]
        planes=read_canonical_planes(image,transform,slices,config.slab_slices)
        fig,axes=plt.subplots(2,3,figsize=(15,8),constrained_layout=True)
        axial=np.asarray(image.dataobj[:,:,k],dtype=np.float32).T
        selected=[b for b in boxes if b['slice_index']==k]
        for rr in (0,1):
            ax=axes[rr,0];ax.imshow(axial,cmap='gray',vmin=-1000,vmax=400,origin='upper',extent=(0,image.shape[0],image.shape[1],0))
            for b in selected:
                x0,y0,x1,y1=b['bounds_scoord_edges'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='#ff8200',linewidth=1.4))
            ax.set_title(f'Axial raw SOP slice {k}: {len(selected)} boxes');ax.set_xlabel('column, pixel-edge coordinates');ax.set_ylabel('row (top → bottom)')
            if rr:
                x0=min(b['bounds_scoord_edges'][0] for b in selected);y0=min(b['bounds_scoord_edges'][1] for b in selected)
                x1=max(b['bounds_scoord_edges'][2] for b in selected);y1=max(b['bounds_scoord_edges'][3] for b in selected)
                ax.set_xlim(max(0,x0-15),min(image.shape[0],x1+15));ax.set_ylim(min(image.shape[1],y1+15),max(0,y0-15))
        canonical_affine=image.affine@nib.orientations.inv_ornt_aff(transform,image.shape)
        spacing=np.linalg.norm(canonical_affine[:3,:3],axis=0)
        for column,axis,name in ((1,1,'Coronal'),(2,0,'Sagittal')):
            plane=planes[axis];overlay=np.take(label,slices[axis],axis=axis).T
            h,v=[a for a in range(3) if a!=axis];extent=(0,plane.shape[1]*spacing[h],0,plane.shape[0]*spacing[v])
            for rr in (0,1):
                ax=axes[rr,column];ax.imshow(plane,cmap='gray',vmin=-1000,vmax=400,origin='lower',extent=extent)
                ax.contour(overlay,levels=[.5],colors=['#ff8200'],origin='lower',extent=extent,linewidths=.7)
                ax.set_title(name+' native axis permutation; bbox envelope');ax.set_xlabel('mm');ax.set_ylabel('mm')
                if rr:
                    yy,xx=np.where(overlay);ax.set_xlim(max(0,xx.min()-15)*spacing[h],min(plane.shape[1],xx.max()+16)*spacing[h])
                    ax.set_ylim(max(0,yy.min()-15)*spacing[v],min(plane.shape[0],yy.max()+16)*spacing[v])
        label_origin='SYNTHETIC FIXTURE' if report['real_data'] is False else 'Lung-PET-CT-Dx / Li et al.; expert SR / Krishnaswamy et al. IDC | CC BY 4.0'
        fig.suptitle(f"{row['patient_id']} CT {row['series_uid'][-18:]} | {row['box_count']} boxes, {row['annotated_slice_count']}/{image.shape[2]} positive slices\n{label_origin}\nOrange = weak bbox, NOT segmentation GT; unannotated = UNKNOWN; display window [-1000,400] HU",fontsize=10)
        destination=Path(config.qa_dir)/(row['case_id']+'_qa.png');destination.parent.mkdir(parents=True,exist_ok=True)
        fig.savefig(destination,dpi=110);plt.close(fig)
        records.append({'case_id':row['case_id'],'file':destination.name,'png_sha256':file_sha256(destination),
                        'axial_raw_slice_index':k,'axial_box_count':len(selected),'source_image_sha256':row['image_sha256'],
                        'source_bbox_sha256':row['bbox_sha256'],'manual_review':'pending'})
    output={'timestamp_utc':utc_now(),'real_data':report['real_data'],'cases':records,'n_cases':len(records),
            'actionable_findings':bool(not records or report.get('actionable_findings')),
            'status':'REVIEW_REQUIRED' if records else 'NO_CONVERTED_CASES',
            'manifest_sha256':report['manifest_sha256'],'implementation':identity,'manual_review':'pending; rendering is not anatomical approval'}
    write_json(Path(config.qa_dir)/'qa_index.json',output)
    return output
