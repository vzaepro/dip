import collections
import contextlib
import tempfile
from copy import deepcopy

import mock
import pytest
from dip import config
from dip import exc
from . import CONFIG


@contextlib.contextmanager
def tempcfg():
    yield config.DipConfig(**deepcopy(CONFIG.config))


@mock.patch('easysettings.JSONSettings.from_file')
def test_load_err(mock_file):
    mock_file.side_effect = IOError
    assert dict(config.load()) == {}


def test_DipConfig_str():
    home = '/path/to/dip/config.json'
    assert str(config.DipConfig(home=home)) == home


def test_DipConfig_repr():
    home = '/path/to/dip/config.json'
    assert repr(config.DipConfig(home=home)) == \
        "DipConfig({home})".format(home=home)


def test_DipConfig_del():
    with tempcfg() as cfg:
        del cfg['fizz']
        assert 'fizz' not in cfg.config['dips']


def test_DipConfig_set():
    with tempcfg() as cfg:
        cfg['foo'] = {'fizz': 'buzz'}
        assert 'foo' in cfg.config['dips']


@mock.patch('dip.config.DipConfig.save')
@mock.patch('dip.config.Dip')
@mock.patch('dip.utils.write_exe')
def test_DipConfig_install(mock_exe, mock_dip, mock_save):
    with tempcfg() as cfg:
        cfg.install('test',
                    '/path/to/test',
                    '/path/to/bin',
                    {'FIZZ': 'BUZZ'},
                    'origin/master')
        mock_dip.assert_called_once_with('test',
                                         '/path/to/test',
                                         '/path/to/bin',
                                         {'FIZZ': 'BUZZ'},
                                         'origin',
                                         'master')
        mock_exe.assert_called_once_with('/path/to/bin', 'test')


@mock.patch('dip.config.DipConfig.save')
@mock.patch('dip.config.Dip')
@mock.patch('dip.utils.write_exe')
def test_DipConfig_install_no_branch(mock_exe, mock_dip, mock_save):
    with tempcfg() as cfg:
        cfg.install('test',
                    '/path/to/test',
                    '/path/to/bin',
                    {'FIZZ': 'BUZZ'},
                    'origin')
        mock_dip.assert_called_once_with('test',
                                         '/path/to/test',
                                         '/path/to/bin',
                                         {'FIZZ': 'BUZZ'},
                                         'origin',
                                         None)
        mock_exe.assert_called_once_with('/path/to/bin', 'test')


@mock.patch('easysettings.JSONSettings.save')
def test_DipConfig_save_err(mock_save):
    mock_save.side_effect = IOError
    with pytest.raises(exc.DipConfigError):
        CONFIG.save()


@mock.patch('dip.config.DipConfig.save')
def test_DipConfig_uninstall(mock_save):
    with tempcfg() as cfg:
        cfg.uninstall('fizz')
        assert 'fizz' not in cfg.config['dips']


def test_Dip_str():
    assert str(config.Dip('fizz', '/path/to/fizz', '/bin')) == 'fizz'


def test_Dip_repr():
    assert repr(config.Dip('fizz', '/path/to/fizz', '/bin')) == 'Dip(fizz)'


@mock.patch('compose.config.config.get_default_config_files')
def test_Dip_definition(mock_cfg):
    with tempfile.NamedTemporaryFile() as tmp:
        mock_cfg.return_value = [tmp.name]
        tmp.write('SAMPLE'.encode('utf-8'))
        tmp.flush()
        dip = config.Dip('fizz', '/path/to/fizz', '/bin')
        assert dip.definition == 'SAMPLE'


@mock.patch('git.Repo')
@mock.patch('compose.config.config.get_default_config_files')
@mock.patch('subprocess.check_output')
@mock.patch('subprocess.call')
@mock.patch('time.sleep')
def test_Dip_diff(mock_time, mock_call, mock_check, mock_cfg, mock_repo):
    mock_repo.working_dir = '/path/to/git'
    mock_cfg.return_value = ['/path/to/fizz/docker-compose.yml']
    mock_check.return_value = 'DIFF'
    dip = config.Dip('fizz', '/path/to/fizz', '/bin', {}, 'origin', 'master')
    dip.diff()
    mock_call.assert_called_once_with([
        'git', '--no-pager', 'diff',
        'origin/master:path/to/fizz/docker-compose.yml',
        '/path/to/fizz/docker-compose.yml'])


@mock.patch('subprocess.check_output')
@mock.patch('os.execv')
def test_Dip_run(mock_exec, mock_subp):
    env = collections.OrderedDict([('FIZZ', 'BUZZ'), ('JAZZ', 'FUNK')])
    dip = config.Dip('fizz', '/path/to/fizz', '/bin', env)
    mock_subp.return_value = '/bin/docker-compose'
    dip.run()
    mock_exec.assert_called_once_with(
        '/bin/docker-compose',
        ['docker-compose', 'run', '--rm',
         '-e', 'FIZZ=BUZZ',
         '-e', 'JAZZ=FUNK',
         'fizz'])
