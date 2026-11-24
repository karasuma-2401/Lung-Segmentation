"""Export minimal official IDC index metadata for T06; no DICOM downloads."""
import argparse
from pathlib import Path
import sys
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--index',type=Path,required=True)
parser.add_argument('--duckdb-path',type=Path)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.duckdb_path:sys.path.insert(0,str(args.duckdb_path.resolve()))
import duckdb
from lungseg.data.msd_acquire import file_sha256
from lungseg.runs import write_json
relation=duckdb.connect().execute("SELECT collection_id, analysis_result_id, PatientID, StudyInstanceUID, SeriesInstanceUID, Modality, source_DOI, license_short_name, instanceCount, series_size_MB, series_aws_url FROM read_parquet(?) WHERE collection_id='lung_pet_ct_dx' AND (lower(source_DOI)='10.7937/tcia.2020.nnc2-0461' OR lower(source_DOI)='10.5281/zenodo.16989819') ORDER BY PatientID,StudyInstanceUID,SeriesInstanceUID",[str(args.index)])
names=[x[0] for x in relation.description]
rows=[dict(zip(names,r)) for r in relation.fetchall()]
write_json(args.output,{'source':'https://storage.googleapis.com/idc-index-data-artifacts/current/release_artifacts/idc_index.parquet',
                      'index_sha256':file_sha256(args.index),'series':rows})
print(f'{len(rows)} original CT/PT + expert SR series exported; no AI SEG')
