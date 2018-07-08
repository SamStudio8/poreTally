import helper_functions as hp
import shutil
import yaml
import os
import warnings
import snakemake
import datetime


def main(args):
    __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    fastq_list = hp.parse_input_path(args.reads_dir, pattern='*.fastq')
    wd = hp.parse_output_path(args.working_dir)

    # Make necessary subdirs
    wd_results = hp.parse_output_path(wd + 'assembler_results/')
    wd_assemblies = hp.parse_output_path(wd_results + 'assemblies/')
    wd_logs = hp.parse_output_path(wd_results + 'log_files/')
    wd_cpu = hp.parse_output_path(wd_results + 'cpu_files/')
    wd_condas = hp.parse_output_path(wd_results + 'conda_files/')
    wd_commands = hp.parse_output_path(wd_results + 'command_files/')

    if os.path.exists(wd+'Snakefile'):
        os.remove(wd+'Snakefile')

    # merge fastq's
    all_reads_fastq = wd + 'all_reads.fastq'
    with open(all_reads_fastq, 'wb') as afq:
        for f in fastq_list:
            with open(f, 'rb') as fd:
                shutil.copyfileobj(fd, afq)

    param_dict = dict()
    param_dict['NB_THREADS'] = args.threads_per_job
    param_dict['REFGENOME_SIZE'] = hp.get_nb_bases(args.ref_fasta, 'fasta')
    param_dict['SEQUENCED_SIZE'] = hp.get_nb_bases(all_reads_fastq, 'fastq')
    param_dict['COVERAGE'] = param_dict['SEQUENCED_SIZE'] / param_dict['REFGENOME_SIZE']
    param_dict['WD'] = wd

    # Construct Snakefile
    # construct unique name for snakefile first
    sf_fn = wd + 'Snakefile_assemblies_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    cmds_dict = dict()
    sf_dict = dict()
    for pipeline in args.pipelines:
        yaml_fn = __location__ + '/assembler_commands/' + pipeline + '.yaml'
        if os.path.exists(yaml_fn):
            with open(yaml_fn, 'r') as plf:
                pl_dict = yaml.load(plf)
        else:
            warnings.warn('Could not find yaml file for {pl}, skipping'.format(pl=yaml_fn))
            continue

        wd_cur = hp.parse_output_path(wd_results + pipeline)
        sf_dict[pipeline] = {
            'input': {'fastq': wd+'all_reads.fastq'},
            'threads': [args.threads_per_job],
            'output': [wd_assemblies + pipeline + '.fasta'],
            'log': [wd_logs + pipeline + '.log'],
            'benchmark': [wd_cpu + pipeline + '.bm']
        }
        if args.fast5_dir:
            fast5_dir_abs = os.path.abspath(args.fast5_dir) + '/'
            param_dict['FAST5_DIR'] = fast5_dir_abs

        conda = pl_dict.get('conda')
        if conda:
            with open(wd_condas + pipeline + '.yaml', 'w') as cf:
                yaml.dump(conda, cf, default_flow_style=False)
            sf_dict[pipeline]['conda'] = [wd_condas + pipeline + '.yaml']
        assembly_cmds = pl_dict['commands'].format(**param_dict)
        cmds = list()
        cmds.extend(hp.parse_version_commands(pl_dict['versions'],
                                              pl_dict['description']))
        cmds.append('cd {}'.format(wd_cur))
        cmds.extend(assembly_cmds.split(sep='\n'))
        cmds_dict[pipeline] = cmds
        with open(wd_commands + pipeline + '.cmd', 'w') as f:
            f.write(assembly_cmds)
    sf_string = hp.dict_to_snakefile(cmds_dict, sf_dict)
    with open(sf_fn, 'a') as sf:
        sf.write(sf_string)
    
    snakemake.snakemake(sf_fn,
                        targets=args.pipelines,
                        use_conda=True)