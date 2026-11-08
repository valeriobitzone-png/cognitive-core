import os
import stat
import pytest
from worldcore import WorldCore


@pytest.mark.skipif(os.name!='posix',reason='POSIX directory modes')
def test_opening_database_does_not_restrict_existing_project_folder(tmp_path):
    project=tmp_path/'existing_project';project.mkdir();project.chmod(0o755)
    with WorldCore(project/'worker.db'):pass
    assert stat.S_IMODE(project.stat().st_mode)==0o755
    assert stat.S_IMODE((project/'worker.db').stat().st_mode)==0o600


@pytest.mark.skipif(os.name!='posix',reason='POSIX directory modes')
def test_new_private_database_directory_is_restricted(tmp_path):
    folder=tmp_path/'new_private_folder'
    with WorldCore(folder/'worker.db'):pass
    assert stat.S_IMODE(folder.stat().st_mode)==0o700
