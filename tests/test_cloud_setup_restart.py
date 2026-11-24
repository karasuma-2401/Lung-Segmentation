"""Restart staging tests with a tiny synthetic tar; no network/Linux claims."""
from io import BytesIO
import importlib.util
from pathlib import Path
import tarfile
import pytest

spec=importlib.util.spec_from_file_location('restart_cell',Path(__file__).parents[1]/'docs/evidence/p1_r_1/notebook_cells/02c_setup_from_attached_dataset.py')
cell=importlib.util.module_from_spec(spec);spec.loader.exec_module(cell)


def synthetic_tar(tmp_path,names=None):
    path=tmp_path/'synthetic_transfer.bin'
    with tarfile.open(path,'x') as handle:
        for name in names or ['pilot_input/fixture.txt','code/fixture.py']:
            raw=b'SYNTHETIC_ONLY';info=tarfile.TarInfo(name);info.size=len(raw);handle.addfile(info,BytesIO(raw))
    return path


def extract(source,stage,count=2):
    cell.extract_verified(source,stage,cell.file_sha(source),source.stat().st_size,count)


def test_restart_from_persistent_input_does_not_need_old_cache(tmp_path):
    archive=synthetic_tar(tmp_path);first=tmp_path/'session1';second=tmp_path/'session2'
    extract(archive,first);extract(archive,second)
    assert (first/'pilot_input/fixture.txt').read_bytes()==(second/'pilot_input/fixture.txt').read_bytes()
    assert not (second/'repo').exists()  # Source checkout is a separate explicit step, not assumed.


def test_corrupted_transfer_rejected_before_stage_creation(tmp_path):
    archive=synthetic_tar(tmp_path);stage=tmp_path/'stage'
    with pytest.raises(AssertionError,match='integrity'):
        cell.extract_verified(archive,stage,'0'*64,archive.stat().st_size,2)
    assert not stage.exists()


@pytest.mark.parametrize('name',['../escape','/absolute','code/../escape','pilot_input/a\\b','code/C:bad'])
def test_unsafe_tar_paths_rejected_before_writes(tmp_path,name):
    archive=synthetic_tar(tmp_path,[name]);stage=tmp_path/'stage'
    with pytest.raises(AssertionError):extract(archive,stage,1)
    assert not stage.exists()


def test_existing_stage_preserved(tmp_path):
    archive=synthetic_tar(tmp_path);stage=tmp_path/'stage';stage.mkdir();(stage/'keep').write_bytes(b'preserve')
    with pytest.raises(AssertionError,match='Fresh'):extract(archive,stage)
    assert (stage/'keep').read_bytes()==b'preserve'
