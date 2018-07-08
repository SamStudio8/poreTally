import os
import sys
import fnmatch
import yaml
import warnings
from Bio import SeqIO
from git import Repo, GitCommandError
import tempfile
from pathlib import Path
from shutil import rmtree


def parse_output_path(location):
    """
    Take given path name. Add '/' if path. Check if exists, if not, make dir and subdirs.
    """
    location = os.path.abspath(location) + '/'
    if not os.path.isdir(location):
        os.makedirs(location)
    return location


def parse_input_path(location, pattern=None):
    """
    Take path, list of files or single file, Return list of files with path name concatenated.
    """
    if not isinstance(location, list):
        location = [location]
    all_files = []
    for loc in location:
        loc = os.path.abspath(loc)
        if os.path.isdir(loc):
            if loc[-1] != '/':
                loc += '/'
            for root, dirs, files in os.walk(loc):
                if pattern:
                    for f in fnmatch.filter(files, pattern):
                        all_files.append(os.path.join(root, f))
                else:
                    for f in files:
                        all_files.append(os.path.join(root, f))
        elif os.path.exists(loc):
            all_files.extend(loc)
        else:
            warnings.warn('Given file/dir %s does not exist, skipping' % loc, RuntimeWarning)
    if not len(all_files):
        ValueError('Input file location(s) did not exist or did not contain any files.')
    return all_files


def parse_version_commands(v_dict, description):
    """
    Take dict with version commands as values and tool names as keys and parse into list
     of strings that will print tool name and version in yaml format in log files.
    """
    cmds = ['echo "START METHODS PRINTING"']
    cmds.append('echo "description: {}"'.format(description).replace('\n', ''))
    cmds.append('echo "versions:"')
    for cv in v_dict:
        cmds.append('echo "  {cv}: "$({version})'.format(cv=cv, version=v_dict[cv]))
    cmds.append('echo "END METHODS PRINTING"')
    return cmds


def get_nb_bases(file, type='fasta'):
    """
    Get number of bases stored in a fasta/fastq file
    """
    lens_list = []
    for seq in SeqIO.parse(file, type):
        lens_list.append(len(seq))
    return sum(lens_list)


def dict_to_snakefile(cmds_dict, sf_dict):
    """
    Convert dicts to string that can serve as input for snakemake
    """
    sf_out = ''
    for rn in sf_dict:
        sf_rule = 'rule {}:\n'.format(rn)
        for rn2 in sf_dict[rn]:
            sf_rule += '\t{}:\n'.format(rn2)
            for l in sf_dict[rn][rn2]:
                if l:
                    if type(sf_dict[rn][rn2]) is dict:
                        sf_rule += '\t\t{k}=\'{v}\',\n'.format(k=l, v=sf_dict[rn][rn2][l].replace('\'', '\\\''))
                    elif type(l) is str:
                        sf_rule += '\t\t\'{}\'\n'.format(l.replace('\'', '\\\''))
                    elif type(l) is int:
                        sf_rule += '\t\t{}\n'.format(l)
        sf_out += sf_rule
        sf_out += '\tshell:\n\t\t\'\'\'\n\t\t'
        for l in cmds_dict[rn]:
            if l:
                if ' > ' in l:
                    sf_out += 'echo $({} 2>&1 ) >> {{log}} 2>&1\n\t\t'.format(l)
                else:
                    sf_out += '{} >> {{log}} 2>&1\n\t\t'.format(l)
        sf_out += '\'\'\'\n\n'
    return sf_out


def set_remote_safely(repo_obj, remote_name, url):
    remotes_list = [cur_remote.name for cur_remote in repo_obj.remotes]
    if remote_name in remotes_list:
        repo_obj.remote(remote_name).set_url(url)
        remote_obj = repo_obj.remote(remote_name)
    else:
        remote_obj = repo_obj.create_remote(url=url, name=remote_name)
    return remote_obj


# ---- Arg check functions ----
def is_fasta(filename):
    """
    Check whether file is existing, and if so, check if in fasta format.
    """
    if not os.path.isfile(filename):
        return False
    with open(filename, "r") as handle:
        fasta = SeqIO.parse(handle, "fasta")
        return any(fasta)


def is_user_info_yaml(filename):
    """
    Check whether file is existing, and if so, check if in fasta format.
    """
    if not os.path.isfile(filename):
        return False
    with open(filename, "r") as handle:
        content = yaml.load(handle)
    if not type(content) is dict:
        warnings.warn('{} not read as yaml'.format(filename))
        return False
    required_info = ['authors', 'organism', 'basecaller', 'flowcell', 'kit']
    info_list = list(content)
    for ri in required_info:
        if ri not in info_list:
            warnings.warn('{} not in info file, but required'.format(ri))
            return False
    return True


def is_valid_repo(repo_url):
    repo_dir = tempfile.mkdtemp('poreTally_repo_test')
    tst_file = repo_dir+'/push_test.txt'
    Path(tst_file).touch()
    repo_obj = Repo.init(repo_dir)
    _ = repo_obj.index.add(['push_test.txt'])
    _ = repo_obj.index.commit('test write access')
    remote = set_remote_safely(repo_obj, 'push_test', repo_url)
    # remote = repo_obj.create_remote(url=repo_url, name='push_test')
    try:
        _ = remote.push('master:origin')
        _ = repo_obj.index.remove(['push_test.txt'])
        _ = repo_obj.index.commit('remove access test file')
        _ = remote.push('master:origin')
    except GitCommandError as e:
        print('Error encountered while testing write access to repo {url}:\n{err}'.format(url=repo_url, err=e))
        sys.exit(1)
    finally:
        rmtree(repo_dir)
    return repo_url

def is_integer(val):
    if type(val) is int:
        return True
    try:
        int(val)
        return True
    except ValueError:
        return False
