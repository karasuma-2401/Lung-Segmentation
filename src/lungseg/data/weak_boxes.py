"""Surveyed expert bbox SR (IDC 2025), never segmentation GT or implicit negatives."""
from collections import Counter
import numpy as np
from pydicom.uid import CTImageStorage, Comprehensive3DSRStorage
from lungseg.data.dicom_geometry import DataIssue


def code(item, sequence='ConceptNameCodeSequence'):
    seq = getattr(item, sequence, [])
    return (str(seq[0].CodingSchemeDesignator),str(seq[0].CodeValue),str(seq[0].CodeMeaning)) if len(seq)==1 else None


def walk(item):
    for child in getattr(item,'ContentSequence',[]):
        yield child
        yield from walk(child)


def evidence_reference(sr):
    if str(sr.Modality) != 'SR' or str(sr.SOPClassUID) != str(Comprehensive3DSRStorage):
        raise DataIssue('unsupported_annotation_sop_class')
    references = []
    for study in getattr(sr,'CurrentRequestedProcedureEvidenceSequence',[]):
        for series in getattr(study,'ReferencedSeriesSequence',[]):
            sops = {}
            for image in getattr(series,'ReferencedSOPSequence',[]):
                uid = str(image.ReferencedSOPInstanceUID)
                if uid in sops: raise DataIssue('duplicate_evidence_sop')
                if str(image.ReferencedSOPClassUID) != str(CTImageStorage): raise DataIssue('annotation_references_non_ct')
                sops[uid] = str(image.ReferencedSOPClassUID)
            references.append({'study_uid':str(study.StudyInstanceUID),'series_uid':str(series.SeriesInstanceUID),'sop_uids':sorted(sops)})
    if len(references) != 1 or not references[0]['sop_uids']:
        raise DataIssue('ambiguous_or_missing_annotation_ct_reference')
    return references[0]


def rectangle_bounds(points):
    p = np.asarray(points,dtype=float)
    if p.shape != (10,) or not np.isfinite(p).all(): raise DataIssue('invalid_bbox_coordinates')
    p = p.reshape(5,2)
    if not np.array_equal(p[0],p[-1]): raise DataIssue('bbox_polyline_not_closed')
    lo,hi = p.min(axis=0),p.max(axis=0)
    if (hi <= lo).any(): raise DataIssue('degenerate_bbox')
    corners = {(float(x),float(y)) for x in (lo[0],hi[0]) for y in (lo[1],hi[1])}
    if set(map(tuple,p[:4])) != corners or any(np.count_nonzero(b-a) != 1 for a,b in zip(p[:-1],p[1:])):
        raise DataIssue('non_rectangular_or_crossed_bbox')
    return [float(lo[0]),float(lo[1]),float(hi[0]),float(hi[1])]


def parse_sr(sr):
    ref = evidence_reference(sr)
    templates = getattr(sr,'ContentTemplateSequence',[])
    if len(templates)!=1 or str(templates[0].TemplateIdentifier)!='1500': raise DataIssue('unsupported_sr_template')
    records,tracking = [],set()
    groups = [n for n in walk(sr) if code(n) and code(n)[:2]==('DCM','125007')]
    all_regions = [n for n in walk(sr) if str(getattr(n,'ValueType','')) in ('SCOORD','SCOORD3D')]
    processed = 0
    for group_index,group in enumerate(groups):
        children = list(getattr(group,'ContentSequence',[]))
        finding = [code(n,'ConceptCodeSequence') for n in children if code(n) and code(n)[:2]==('DCM','121071')]
        tids = [str(n.UID) for n in children if code(n) and code(n)[:2]==('DCM','112040')]
        regions = [n for n in children if str(getattr(n,'ValueType','')) in ('SCOORD','SCOORD3D')]
        if len(finding)!=1 or finding[0] is None or len(tids)!=1 or len(regions)!=1:
            raise DataIssue('ambiguous_measurement_group',f'group={group_index}')
        if tids[0] in tracking: raise DataIssue('duplicate_annotation_tracking_uid')
        tracking.add(tids[0])
        region = regions[0]
        if region.ValueType!='SCOORD' or str(getattr(region,'GraphicType',''))!='POLYLINE' or str(getattr(region,'PixelOriginInterpretation','FRAME'))!='FRAME':
            raise DataIssue('unsupported_bbox_coordinate_semantics')
        images = list(getattr(region,'ContentSequence',[]))
        if len(images)!=1 or images[0].ValueType!='IMAGE' or images[0].RelationshipType!='SELECTED FROM':
            raise DataIssue('ambiguous_bbox_image_reference')
        refs = getattr(images[0],'ReferencedSOPSequence',[])
        if len(refs)!=1 or str(refs[0].ReferencedSOPClassUID)!=str(CTImageStorage) or hasattr(refs[0],'ReferencedFrameNumber'):
            raise DataIssue('unsupported_bbox_image_reference')
        sop = str(refs[0].ReferencedSOPInstanceUID)
        if sop not in ref['sop_uids']: raise DataIssue('bbox_sop_missing_from_evidence')
        bounds = rectangle_bounds(region.GraphicData)
        records.append({'group_index':group_index,'tracking_uid':tids[0],'sop_uid':sop,
                        'bounds_scoord_edges':bounds,'graphic_data':list(map(float,region.GraphicData)),
                        'finding_code':list(finding[0]),'coordinate_convention':'dicom_scoord_pixel_edges'})
        processed += 1
    if processed != len(all_regions): raise DataIssue('unparsed_annotation_regions')
    duplicates = Counter((r['sop_uid'],tuple(r['bounds_scoord_edges'])) for r in records)
    return {'patient_id':str(sr.PatientID),'sr_study_uid':str(sr.StudyInstanceUID),'sr_series_uid':str(sr.SeriesInstanceUID),
            'sr_sop_uid':str(sr.SOPInstanceUID),'ct_reference':ref,'boxes':records,
            'duplicate_box_geometry_count':sum(n-1 for n in duplicates.values() if n>1),
            'negative_sop_uids':[], 'negative_annotation_support':'not asserted by this SR parser',
            'xml_equivalence':'publisher harmonization; original XML bytes/convention not locally validated'}


def index_bounds(box, shape, convention):
    """Return [x0,y0,x1,y1) with no clipping; conventions must be explicit.

    Production SR uses continuous pixel-edge coordinates: voxel(i,j) center is
    (i+.5,j+.5). Integer edges therefore reduce to zero-based half-open bounds.
    VOC helper exists for explicit math tests, not a claim about inaccessible XML.
    """
    b = np.asarray(box,dtype=float)
    if b.shape!=(4,) or not np.isfinite(b).all(): raise DataIssue('invalid_bbox_coordinates')
    if convention=='voc_one_based_inclusive':
        if not np.equal(b,np.floor(b)).all() or b[2]<b[0] or b[3]<b[1]: raise DataIssue('inverted_bbox')
        b = b + [-1,-1,0,0]
    elif convention=='zero_based_half_open':
        if not np.equal(b,np.floor(b)).all(): raise DataIssue('noninteger_index_bounds')
    elif convention!='dicom_scoord_pixel_edges': raise DataIssue('unknown_bbox_coordinate_convention')
    if b[2]<=b[0] or b[3]<=b[1]: raise DataIssue('inverted_or_degenerate_bbox')
    if b[0]<0 or b[1]<0 or b[2]>shape[0] or b[3]>shape[1]: raise DataIssue('bbox_out_of_bounds')
    if convention=='dicom_scoord_pixel_edges':
        b = np.r_[np.ceil(b[:2]-.5),np.floor(b[2:]-.5)+1]
        if b[2]<=b[0] or b[3]<=b[1]: raise DataIssue('bbox_has_no_voxel_centers')
    return list(map(int,b))


def annotation_coverage(sop_uids, boxes, negative_sop_uids=()):
    counts = Counter(b['sop_uid'] for b in boxes)
    negatives = set(negative_sop_uids)
    if not (counts.keys() | negatives).issubset(sop_uids): raise DataIssue('annotation_sop_not_in_ct')
    if counts.keys() & negatives: raise DataIssue('positive_negative_annotation_conflict')
    return [{'sop_uid':uid,'status':'positive_bbox' if counts[uid] else 'explicit_negative' if uid in negatives else 'missing_unknown',
             'bbox_count':counts[uid]} for uid in sop_uids]


def rasterize_boxes(parsed, geometry):
    ref = parsed['ct_reference']
    if parsed['patient_id']!=geometry.patient_id or ref['study_uid']!=geometry.study_uid or parsed['sr_study_uid']!=geometry.study_uid or ref['series_uid']!=geometry.series_uid:
        raise DataIssue('ct_bbox_identity_mismatch')
    if not set(ref['sop_uids']).issubset(geometry.sop_uids): raise DataIssue('annotation_sop_not_in_ct')
    coverage = annotation_coverage(geometry.sop_uids,parsed['boxes'],parsed['negative_sop_uids'])
    if not parsed['boxes']: raise DataIssue('no_positive_bbox_or_verified_negative')
    volume = np.zeros(geometry.shape,dtype=np.uint8)
    index = {sop:k for k,sop in enumerate(geometry.sop_uids)}
    records=[]
    for box in parsed['boxes']:
        x0,y0,x1,y1 = index_bounds(box['bounds_scoord_edges'],geometry.shape[:2],'dicom_scoord_pixel_edges')
        k = index[box['sop_uid']]
        volume[x0:x1,y0:y1,k]=1
        edges=np.array(box['graphic_data']).reshape(-1,2)-.5
        corners=(geometry.affine_lps @ np.c_[edges,np.full(len(edges),k),np.ones(len(edges))].T).T[:,:3]
        records.append({**box,'slice_index':k,'index_bounds_half_open':[x0,y0,x1,y1],
                        'physical_corners_lps_mm':corners.tolist()})
    return volume,records,coverage
