import contextlib
import json

import click.testing
import docker
import git
import mock
import pytest

import dip
from dip import errors
from dip import main
from . import MockSettings


@contextlib.contextmanager
def invoke(command, args=None):
    runner = click.testing.CliRunner()
    yield runner.invoke(command, args or [])


def test_clickerr():
    mock_func = mock.MagicMock()
    mock_func.side_effect = errors.DipError()
    with pytest.raises(click.ClickException):
        main.clickerr(mock_func)()


def test_dip():
    with invoke(main.dip) as result:
        assert result.exit_code == 0


def test_version():
    with invoke(main.dip, ['--version']) as result:
        assert result.exit_code == 0
        assert result.output == \
            "dip, version {vsn}\n".format(vsn=dip.__version__)


@mock.patch('dip.settings.load')
def test_config_string(mock_load):
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_config, ['fizz', 'env', 'FIZZ']) as result:
        assert result.exit_code == 0
        assert result.output == \
            MockSettings()['fizz']['env']['FIZZ'] + '\n'


@mock.patch('dip.settings.load')
def test_config_json(mock_load):
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_config, ['fizz']) as result:
        assert result.exit_code == 0
        assert result.output == json.dumps(MockSettings().data['fizz'],
                                           indent=4,
                                           sort_keys=True) + '\n'


@mock.patch('dip.settings.load')
def test_config_err(mock_load):
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_config, ['fuzz']) as result:
        assert result.exit_code != 0


@mock.patch('dip.settings.saveonexit')
@mock.patch('dip.settings.Settings.install')
def test_install(mock_ins, mock_load):
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_install, ['fizz', '/test/path',
                                   '--env', 'FIZZ=BUZZ',
                                   '--path', '/path/to/bin',
                                   '--remote', 'origin/master',
                                   '--sleep', '5']):
        mock_ins.assert_called_once_with(
            'fizz', '/test/path', '/path/to/bin',
            {'FIZZ': 'BUZZ'},
            {'remote': 'origin', 'branch': 'master', 'sleep': 5})


@mock.patch('dip.settings.load')
@mock.patch('git.Repo')
def test_list(mock_repo, mock_load):
    mock_repo.return_value.active_branch.name = 'edge'
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_list) as result:
        assert result.exit_code == 0
        assert result.output == '''
buzz /path/to/buzz origin/edge
fizz /path/to/fizz origin/master
jazz /path/to/jazz

'''


@mock.patch('dip.settings.load')
@mock.patch('git.Repo')
def test_list_git_err(mock_repo, mock_load):
    mock_repo.side_effect = git.exc.GitCommandError('test', 'test')
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_list) as result:
        assert result.exit_code == 0
        assert result.output == '''
buzz /path/to/buzz [git error]
fizz /path/to/fizz origin/master
jazz /path/to/jazz

'''


@mock.patch('dip.settings.getapp')
def test_pull(mock_load):
    with invoke(main.dip_pull, ['fizz']) as result:
        mock_load.return_value.__enter__\
            .return_value.service.pull.assert_called_once_with()
        assert result.exit_code == 0


@mock.patch('dip.settings.getapp')
def test_pull_err(mock_load):
    mock_load.return_value.__enter__\
        .return_value.service.pull.side_effect = Exception
    with invoke(main.dip_pull, ['fizz']) as result:
        mock_load.return_value.__enter__\
            .return_value.service.pull.assert_called_once_with()
        assert result.exit_code != 0


@mock.patch('dip.settings.getapp')
@mock.patch('dip.settings.Dip.service')
@mock.patch('dip.settings.Dip.diff')
def test_pull_docker_err(mock_diff, mock_svc, mock_app):
    mock_diff.return_value = False
    mock_app.return_value.__enter__.return_value = MockSettings()['fizz']
    mock_svc.pull.side_effect = docker.errors.APIError('test')
    with invoke(main.dip_pull, ['fizz']) as result:
        assert result.exit_code != 0


@mock.patch('dip.settings.reset')
def test_reset(mock_reset):
    with invoke(main.dip_reset, ['--force']) as result:
        assert result.exit_code == 0
        mock_reset.assert_called_once_with()


@mock.patch('os.remove')
def test_reset_err(mock_rm):
    mock_rm.side_effect = OSError
    with invoke(main.dip_reset, ['--force']) as result:
        assert result.exit_code != 0


@mock.patch('dip.settings.getapp')
def test_run(mock_app):
    with invoke(main.dip_run, ['fizz', '--',
                               '--opt1', 'val1',
                               '--flag']) as result:
        mock_app.return_value.__enter__.return_value.run\
            .assert_called_once_with('--opt1', 'val1', '--flag')
        assert result.exit_code == 0


@mock.patch('dip.settings.getapp')
def test_show(mock_app):
    mock_app.return_value.__enter__.return_value.diff.return_value = False
    mock_app.return_value.__enter__.return_value.definitions = iter(['TEST'])
    with invoke(main.dip_show, ['fizz']) as result:
        assert result.exit_code == 0
        assert result.output == '\nTEST\n\n'


@mock.patch('dip.settings.getapp')
def test_show_sleep(mock_app):
    mock_app.return_value.__enter__.return_value.repo.sleeptime = 10
    mock_app.return_value.__enter__.return_value.diff.return_value = True
    mock_app.return_value.__enter__.return_value.definitions = iter(['TEST'])
    with invoke(main.dip_show, ['fizz']) as result:
        assert result.exit_code == 0
        assert result.output == \
            '\nLocal service has diverged from remote or is inaccessible.\n'\
            'Sleeping for 10s\n\n\nTEST\n\n'


@mock.patch('dip.settings.Settings.uninstall')
@mock.patch('dip.settings.saveonexit')
def test_uninstall(mock_load, mock_un):
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_uninstall, ['fizz']) as result:
        assert result.exit_code == 0
        mock_un.assert_called_once_with('fizz')


@mock.patch('dip.settings.Dip.uninstall')
@mock.patch('dip.settings.saveonexit')
def test_uninstall_err(mock_load, mock_un):
    mock_load.return_value.__enter__.return_value = MockSettings()
    with invoke(main.dip_uninstall, ['fuzz']) as result:
        assert result.exit_code == 0
        mock_un.assert_not_called()
