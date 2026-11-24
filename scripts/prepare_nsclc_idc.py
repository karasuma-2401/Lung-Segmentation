"""Export minimal official IDC metadata. Optional duckdb needed only for this script.

Download idc_index.parquet from the documented official IDC artifact URL first;
no DICOM objects are downloaded here. No demographics or clinical dates exported.
"""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--index", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--duckdb-path", type=Path)
args = parser.parse_args()
if args.duckdb_path:
    sys.path.insert(0, str(args.duckdb_path.resolve()))
import duckdb
from lungseg.data.msd_acquire import file_sha256
from lungseg.runs import write_json
relation = duckdb.connect().execute(
    "SELECT collection_id, PatientID, SeriesInstanceUID, StudyInstanceUID, Modality, instanceCount, "
    "license_short_name, source_DOI, series_aws_url FROM read_parquet(?) "
    "WHERE collection_id='nsclc_radiomics' AND Modality IN ('CT','RTSTRUCT') "
    "AND lower(source_DOI)='10.7937/k9/tcia.2015.pf0m9rei' ORDER BY PatientID, Modality, SeriesInstanceUID",
    [str(args.index)])
columns = [item[0] for item in relation.description]
rows = [dict(zip(columns, values)) for values in relation.fetchall()]
write_json(args.output, {
    "source": "https://storage.googleapis.com/idc-index-data-artifacts/current/release_artifacts/idc_index.parquet",
    "index_sha256": file_sha256(args.index), "series": rows})
print(json.dumps({"series": len(rows), "output": str(args.output)}))
