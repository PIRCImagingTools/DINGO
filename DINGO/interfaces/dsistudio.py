import os
import time
import shutil
from itertools import compress
from DINGO.utils import (list_to_str,
                         split_filename)
from nipype.interfaces.base import (traits, File, Directory, InputMultiPath, 
                                    OutputMultiPath, isdefined,
                                    CommandLine, CommandLineInputSpec, 
                                    TraitedSpec)
from traits.trait_base import _Undefined

# on_trait_change functions not firing when updating from indict
# _check_mandatory_inputs  updates are currently necessary


class DSIInfo(object):
    # atlas list
    atlases = (
        'aal', 'ATAG_basal_ganglia', 'brodmann', 'Cerebellum-SUIT',
        'FreeSurferDKT', 'Gordan_rsfMRI333', 'HarvardOxfordCort',
        'HarvardOxfordSub', 'HCP-MMP1', 'JHU-WhiteMatter-labels-1mm',
        'MNI', 'OASIS_TRT_20', 'sri24_tissues', 'sri24_tzo116plus',
        'talairach', 'tractography')
    
    # region modification actions
    region_actions = (
        'smoothing', 'erosion', 'dilation', 'defragment', 'negate',
        'flipx', 'flipy', 'flipz',
        'shiftx', 'shiftnx', 'shifty', 'shiftny', 'shiftz', 'shiftnz')
    
    # track, analysis export values
    export_values = (
        'export_stat', 'export_tdi', 'export_tdi2',
        'export_tdi_color', 'export_tdi_end',
        'export_fa', 'export_gfa', 'export_qa', 'export_nqa',
        'export_md', 'export_ad', 'export_rd', 'report')

    # export extension types
    export_texts = ('stat', 'fa', 'gfa', 'qa', 'nqa', 'md', 'ad', 'rd')
    report_texts = ('report_fa', 'report_gfa', 'report_nqa',
                    'report_md', 'report_ad', 'report_rd')
    export_imgs = ('tdi', 'tdi2', 'tdi_color', 'tdi_end', 'tdi2_end')
        
    # file extensions for output types
    ftypes = {
        'SRC':      '.src.gz',
        'FIB':      '.fib.gz',
        'NIFTI':    '.nii.gz',
        'TRK':      '.trk.gz',
        'TXT':      '.txt'}

    # primary output types for action types
    act_out = {
        'trk':  'TRK',
        'rec':  'FIB',
        'src':  'SRC',
        'ana':  'TXT',
        'atl':  'NIFTI'}

    # reconstruction method id for method number
    rec_method_id_n = {
        'dsi':      0,
        'dti':      1,
        'frqbi':    2,
        'shqbi':    3,
        'gqi':      4,
        'qsdr':     7,
        'hardi':    6}
    
    # reconstruction method param types for method id
    rec_param_types = {
        'dsi':      (int,),
        'dti':      tuple(),
        'frqbi':    (int, int),
        'shqbi':    (float, int),
        'gqi':      (float,),
        'qsdr':     (float, int),
        'hardi':    (float, int, float)}
        
    # reconstruction method param ids for method id
    # order matters method id: (param0, param1, param2)
    rec_param_ids = {
        'dsi':      ('hanning_filter_width',),
        'dti':      tuple(),
        'frqbi':    ('interp_kernel_width', 'smooth_kernel_width'),
        'shqbi':    ('regularization', 'harmonic_order'),
        'gqi':      ('mddr',),
        'qsdr':     ('mddr', 'output_resolution'),
        'hardi':    ('mddr', 'b_value', 'regularization')}
                
    # reconstruction method input ids for method id
    # NOT DIRECTLY LINKED TO rec_param_ids
    # should include rec_param_ids, but also others, order doesn't matter
    rec_method_id_inputs = {
        'dsi':      ('check_btable', 'hanning_filter_width',
                     'half_sphere', 'scheme_balance'),
        'dti':      ('check_btable', 'output_dif', 'output_tensor'),
        'frqbi':    ('check_btable', 'interp_kernel_width', 
                     'smooth_kernel_width', 'odf_order', 'record_odf', 
                     'num_fiber', 'half_sphere', 'scheme_balance'),
        'shqbi':    ('check_btable', 'harmonic_order', 'regularization',
                     'odf_order', 'record_odf', 'num_fiber', 'half_sphere',
                     'scheme_balance'),
        'gqi':      ('check_btable', 'mddr', 'r2_weighted', 'output_rdi',
                     'odf_order', 'record_odf', 'num_fiber', 'half_sphere',
                     'scheme_balance'),
        'qsdr':     ('check_btable', 'mddr', 'r2_weighted',
                     'output_resolution', 'output_mapping', 'output_jac',
                     'output_rdi', 'odf_order', 'record_odf', 'csf_cal',
                     'interpolation', 'regist_method', 'num_fiber', 
                     'half_sphere', 'scheme_balance'),
        'hardi':   ('check_btable', 'mddr', 'regularization', 'b_value',
                    'num_fiber', 'half_sphere', 'scheme_balance')}

    @classmethod
    def ot_to_ext(cls, output_type):
        """Get file extension for given output type

        Parameters
        ----------
        output_type : {'SRC', 'FIB', 'NIFTI', 'TRK', 'TXT'}
            String specifying the output type

        Returns
        -------
        extension : str
            The file extension for the output type
        """

        try:
            return cls.ftypes[output_type]
        except KeyError:
            msg = 'Invalid DSIStudioOUTPUTTYPE: %s' % output_type
            raise KeyError(msg)

    @classmethod
    def a_to_ot(cls, action_type):
        """Get DSI studio output extension per action type
        
        Parameter
        ---------
        action : {'src', 'rec', 'trk', 'ana', 'atl'}
            String specifying the action type

        Returns
        -------
        extension : str
            The file extension for the action type
        """

        try:
            return cls.act_out[action_type]
        except KeyError:
            msg = 'Invalid DSIStudioACTIONTYPE: %s' % action_type
            raise KeyError(msg)
            
    @classmethod
    def rec_mid_to_mn(cls, method_id):
        """Get DSI Studio reconstruction method number from id
        
        Parameter
        ---------
        method_id : Str
            specifying reconstruction method number
        
        Returns
        -------
        method_n : Int
        """
        try:
            return cls.rec_method_id_n[method_id]
        except KeyError:
            msg = 'Invalid DSIStudio Reconstruction method: %s' % method_id
            raise KeyError(msg)
            
    @classmethod
    def rec_mid_to_np(cls, method_id):
        """Get number of params per reconstruction method
        
        Parameter
        ---------
        method : {'DSI', 'DTI', 'FRQBI', 'SHQBI', 'GQI', 'HARDI', 'QSDR'}
            Str specifying reconstruction method
        
        Returns
        -------
        Int
        """
        try:
            return len(cls.rec_param_ids[method_id])
        except KeyError:
            msg = 'Invalid DSIStudio Reconstruction method: %s' % method_id
            raise KeyError(msg)
            
    @classmethod
    def rec_mid_to_ptype(cls, method_id):
        """Get param types per tracking method
        
        Parameter
        ---------
        method : {'DSI', 'DTI', 'FRQBI', 'SHQBI', 'GQI', 'HARDI', 'QSDR'}
            Str specifying reconstruction method
        
        Returns
        -------
        type
        """
        try:
            return cls.rec_param_types[method_id]
        except KeyError:
            msg = 'Invalid DSIStudio Reconstruction method: %s' % method_id
            raise KeyError(msg)
            
    @classmethod
    def rec_mid_to_pids(cls, method_id):
        """Get param input ids per reconstruction method
        
        Parameter
        ----------
        method_id   :   Str
        
        Return
        ------
        Tuple(Str)
        """
        try:
            return cls.rec_param_ids[method_id]
        except KeyError:
            msg = 'Invalid DSIStudio Reconstruction method: %s' % method_id
            raise KeyError(msg)
            
    @classmethod
    def rec_mid_to_req(cls, method_id):
        """Get required inputs per reconstruction method"""
        try:
            return cls.rec_method_id_inputs[method_id]
        except KeyError:
            msg = 'Invalid DSIStudio Reconstruction method: %s' % method_id
            raise KeyError(msg)


class DSIStudioInputSpec(CommandLineInputSpec):
    """Base input specification for DSI Studio commands."""

    action = traits.Enum(
        'trk', 'ana', 'src', 'rec', 'atl', 'exp', 'cnt', 'vis', 'ren',
        argstr='--action=%s',
        mandatory=True,
        desc='Command action type to execute',
        position=1)
    source = traits.Either(
        File(exists=True),
        Directory(exists=True),
        mandatory=True,
        argstr='--source=%s',
        desc='Input file to process',
        position=2)
    debuglog = File(
        argstr='> %s',
        position=-1,
        desc='Log file path/name')
    indict = traits.Dict(
        desc='Dict of keys for inputspec, with their values. '
             'Will overwrite all conflicts')


class DSIStudioOutputSpec(TraitedSpec):
    debuglog = File(desc='path/name of log file (if generated)')
    

class DSIStudioCommand(CommandLine):
    """Base support for DSI Studio commands.
    """
    _cmd = 'dsi_studio'
    _output_type = None
    _action = None
    terminal_output = 'file'

    input_spec = DSIStudioInputSpec

    def __init__(self, **inputs):
        super(DSIStudioCommand, self).__init__(**inputs)
        self.inputs.on_trait_change(self._output_update, 'output_type')
        self.inputs.on_trait_change(self._action_update, 'action')
        self.inputs.on_trait_change(self._update_from_indict, 'indict')

        if self._action is None:  # should be specified in subclass
            raise Exception('Missing action command')

        if self._output_type is None:
            self._output_type = DSIInfo.a_to_ot(self._action)

        if not isdefined(self.inputs.output_type):
            self.inputs.output_type = self._output_type
        else:
            self._output_update()

        if not isdefined(self.inputs.action):
            self.inputs.action = self._action
        else:
            self._action_update()
        self._update_from_indict()

    @property
    def action(self):
        return self._action

    def _output_update(self):
        self._output_type = self.inputs.output_type

    def _action_update(self):
        self._action = self.inputs.action
        
    def _update_from_indict(self):
        """Check indict for values to add to inputs"""
        if isdefined(self.inputs.indict):
            for key, value in self.inputs.indict.iteritems():
                if key in self.inputs.__dict__:
                    setattr(self.inputs, key, value)
                    # print('Input: '%s' set to Value: %s' % (key, value))
                    # Type checking is handled by traits InputSpec

    def _gen_fname(self,
                   basename,
                   cwd=None,
                   suffix=None,
                   change_ext=True,
                   ext=None):
        """Generate a filename based on input.
        
        Parameters
        ----------
        basename    : str (filename to base the new filename)
        cwd         : str (path to prefix the new filename)
        suffix      : str (suffix to add to the basename)
        change_ext  : bool (flag to change the filename extension to
            corresponding output type for action)

        Returns
        -------
        fname       : str (new filename based on input)
        """
        remove_ends = (
            ('.src.gz', 3),
            ('.fib.gz', 3),
            ('.nii.gz', 7),
            ('.trk.gz', 7),
            ('.trk.txt', 8),
            ('.txt', 4))

        if basename == '':
            raise ValueError('Unable to generate filename for command {}.'
                             .format(self.cmd))
        if cwd is None:
            cwd = os.getcwd()
        if ext is None:
            ext = DSIInfo.ot_to_ext(self.inputs.output_type)
        if change_ext:
            for ending in remove_ends:
                if basename.endswith(ending[0]):
                    basename = basename[0:len(basename)-ending[1]]
            if suffix:
                suffix = ''.join((suffix, ext))
            else:
                suffix = ext
        if suffix is None:
            suffix = ''
        return os.path.join(os.path.abspath(cwd), ''.join((basename, suffix)))

    def _format_arg(self, name, trait_spec, value):
        if name == 'debuglog':
            argstr = trait_spec.argstr
            if os.path.exists(value):
                returnstr = argstr % value
            else:
                srcpath, _, _ = split_filename(getattr(self.inputs, 'source'))
                returnstr = argstr % os.path.join(srcpath, value)
        else:
            return super(DSIStudioCommand, self)._format_arg(
                name, trait_spec, value)
        return returnstr
        

class DSIStudioFiberInputSpec(DSIStudioInputSpec):
    """Provides region and post-processing input
    specification used with DSI Studio trk and ana actions.
    """
    # ROI Parameters
    seed = File(
        exists=True,
        # DSI Studio has built in accepted values that are not file paths,
        # but AtlasName:RegionName
        # can't check for atlas ids this way, or lose exists check, so split, but not xor
        # traits.Str(requires=['atlas']),
        argstr='--seed=%s',
        desc='specify seeding file, txt, analyze, or nifti, '
             'unspecified default is whole brain')
    seed_actions = traits.List(
        traits.List(traits.Enum(*DSIInfo.region_actions)),
        sep=',',
        desc='action codes to modify seed region')
    rois = InputMultiPath(
        File(exists=True),
        argstr='--roi%s=%s',
        desc='roi through which tracts must pass, txt, analyze, nifti')
    rois_actions = traits.List(
        traits.List(traits.Enum(*DSIInfo.region_actions)),
        sep=',',
        desc='action codes to modify rois, list for each roi')
    roas = InputMultiPath(
        File(exists=True),
        argstr='--roa%s=%s',
        desc='roa files which tracts must avoid, txt, analyze, nifti')
    roas_actions = traits.List(traits.List(
        traits.Enum(*DSIInfo.region_actions)),
        sep=',',
        desc='action codes to modify roas, list for each roa')
    ends = InputMultiPath(
        File(exists=True),
        argstr='--end%s=%s',
        desc='filter out tracks that do not end in this region, '
             'txt, analyze, or nifti')
    ends_actions = traits.List(
        traits.List(traits.Enum(*DSIInfo.region_actions)),
        sep=',',
        desc='action codes to modify ends regions, list for each end')
    ter = InputMultiPath(
        File(exists=True),
        argstr='--ter=%s',
        desc='terminates any track that enters this region, '
             'txt, analyze, or nifti')
    ter_actions = traits.List(
        traits.List(traits.Enum(*DSIInfo.region_actions)),
        sep=',',
        desc='action codes to modify terminative region')
    t1t2 = File(
        exists=True,
        argstr='--t1t2=%s',
        desc='specify t1w or t2w images as roi reference image')
    seed_atlas = traits.Enum(
        *DSIInfo.atlases,
        requires=['seed_ar'],
        sep=',',
        desc='atlas name(s) found in dsistudio/build/atlas')
    rois_atlas = traits.List(
        traits.Enum(*DSIInfo.atlases),
        requires=['rois_ar'],
        sep=',',
        desc='atlas name(s) found in dsistudio/build/atlas')
    roas_atlas = traits.List(
        traits.Enum(*DSIInfo.atlases),
        requires=['roas_ar'],
        sep=',',
        desc='atlas name(s) found in dsistudio/build/atlas')
    ends_atlas = traits.List(
        traits.Enum(*DSIInfo.atlases),
        requires=['ends_ar'],
        sep=',',
        desc='atlas name(s) found in dsistudio/build/atlas')
    ter_atlas = traits.List(
        traits.Enum(*DSIInfo.atlases),
        requires=['ter_ar'],
        sep=',',
        desc='atlas name(s) found in dsistudio/build/atlas')
    seed_ar = traits.Str(
        requires=['seed_atlas'],
        desc='seed region in atlas')
    rois_ar = traits.List(
        traits.Str(),
        requires=['rois_atlas'],
        desc='region in atlas through which tracts must pass')
    roas_ar = traits.List(
        traits.Str(),
        requires=['roas_atlas'],
        desc='region in atlas which tracts must avoid')
    ends_ar = traits.List(
        traits.Str(),
        requires=['ends_atlas'],
        desc='region in atlas that will filter out tracks that do not end here')
    ter_ar = traits.List(
        traits.Str(),
        requires=['ter_atlas'],
        desc='region in atlas, terminates any track that enters')
    
    # Post-Process Parameters
    delete_repeat = traits.Enum(
        0, 1,
        argstr='--delete_repeat=%d',
        desc='0 or 1, 1 removes repeat tracks with distance < 1 mm')
        
    output = traits.Either(
        File(genfile=True), traits.Enum('no_file'),
        genfile=True,
        argstr='--output=%s',
        hash_files=False,
        desc='output tract file name, format may be txt, trk, or nii',
        position=3)
        
    tract_name = traits.Str(desc='prefix to append to source filename')
        
    endpt = traits.Bool(
        argstr='--end_point=%s',
        requires=['endpt_format'],
        desc='whether to output endpoints file')
        
    endpt_format = traits.Enum(
        'txt', 'mat',
        usedefault=True,
        desc='endpoint file format, "txt" or "mat"')
    
    export = traits.List(
        traits.Str(),  # cannot use Enum as report is dynamic
        argstr='--export=%s', 
        sep=', ',
        desc='export information related to fiber tracts')
        
    export_stat = traits.Bool(
        desc='export statistics along tract or in region')
    export_tdi = traits.Bool(
        desc='export tract density image')
    export_tdi2 = traits.Bool(
        desc='export tract density image in subvoxel diffusion space')
    export_tdi_color = traits.Bool(
        desc='export tract color density image')
    export_tdi_end = traits.Bool(
        desc='export tract density image endpoints')
    export_tdi2_end = traits.Bool(
        desc='export tract density image endpoints in subvoxel diffusion space')
    export_fa = traits.Bool(
        desc='export along tract fractional anisotropy values')
    export_gfa = traits.Bool(
        desc='export along tract generalized fractional anisotropy values')
    export_qa = traits.Bool(
        desc='export along tract quantitative anisotropy values')
    export_nqa = traits.Bool(
        desc='export along tract normalized quantitative anisotropy values')
    export_md = traits.Bool(
        desc='export along tract mean diffusivity values')
    export_ad = traits.Bool(
        desc='export along tract axial diffusivity values')
    export_rd = traits.Bool(
        desc='export along tract radial diffusivity values')
    
    report = traits.Bool(
        desc='export tract reports with specified profile style and bandwidth',
        requires=['report_val', 'report_pstyle', 'report_bandwidth'],
        sep=':')
    report_val = traits.Enum(
        'fa', 'gfa', 'qa', 'nqa', 'md', 'ad', 'rd',
        argstr='%s',
        desc='type of value for tract report')
    report_pstyle = traits.Enum(
        0, 1, 2, 3, 4,
        argstr='%d',
        requires=['export'],
        desc='profile style for tract report 0:x, 1:y, 2:z, '
             '3:along tracts, 4:tract mean')
    report_bandwidth = traits.Int(
        argstr='%d',
        requires=['export'],
        desc='bandwidth for tract report')
    report_fa = traits.Bool(desc='export tract report on fa values')
    report_gfa = traits.Bool(desc='export tract report on gfa values')
    report_qa = traits.Bool(desc='export tract report on qa values')
    report_nqa = traits.Bool(desc='export tract report on nqa values')
    report_md = traits.Bool(desc='export tract report on md values')
    report_ad = traits.Bool(desc='export tract report on ad values')
    report_rd = traits.Bool(desc='export tract report on rd values')
        
    connectivity = InputMultiPath(
        File(exists=True),
        argstr='--connectivity=%s',
        sep=',',
        desc='atlas id(s), or path to MNI space roi file')
    connectivity_atlas = traits.List(
        traits.Enum(*DSIInfo.atlases),
        desc='atlas region id(s)')
    connectivity_type = traits.List(
        traits.Enum('end', 'pass'),
        argstr='--connectivity_type=%s',
        sep=',',
        desc='method to count the tracts, default end')
    connectivity_value = traits.List(
        traits.Str(),
        argstr='--connectivity_value=%s',
        sep=',',
        desc='method to calculate connectivity matrix, default count - n tracks'
            ' pass/end in region, ncount - n tracks norm by median length, '
            'mean_length - outputs mean length of tracks, trk - outputs trk '
            'file each matrix entry, other values by reconstruction method, '
            'e.g. "fa","qa","adc", etc.')
    connectivity_threshold = traits.Float(
        0.001,
        argstr='--connectivity_threshold=%.3f',
        desc='threshold for calculating binarized graph measures and '
             'connectivity values, def 0.001, i.e. if the max connectivity count'
             ' is 1000 tracks in the connectivity matrix, then at least '
             '1000 x 0.001 = 1 track is needed to pass the threshold, '
             'otherwise values will be 0')
    ref = File(
        exists=True,
        argstr='--ref=%s',
        desc='output track coordinate based on a reference image, '
             'e.g. T1w or T2w')
    cluster = traits.Bool(
        argstr='--cluster=%d,%d,%d,%s',
        requires=['cluster_method_id', 'cluster_count', 'cluster_res',
                  'cluster_output_fname'],
        desc='whether to run track clustering after fiber tracking')
    cluster_method_id = traits.Enum(
        0, 1, 2,
        desc='0:single-linkage, 1:k-means, 2:EM')
    cluster_count = traits.Int(
        0,
        desc='Total number of clusters assigned in k-means or EM. '
             'In single-linkage, the maximum number of clusters allowed to avoid'
             'over-segmentation.')
    cluster_res = traits.Int(
        0,
        desc='Mini meter resolution for merging clusters in single-linkage')
    cluster_output_fname = traits.Str(
        'cluster_labels.txt',
        desc='Text file name for cluster label output (no spaces)')


class DSIStudioFiberOutputSpec(DSIStudioOutputSpec):
    """Output specification for fiber tracking, trk, ana"""
    output = File(
        desc='path/name of fiber track file (if generated)')
    endpt = File(
        desc='path/name of fiber track end points file (if generated)')
    stat_file = File(
        desc='path/name of fiber track stats file (if generated)')
    tdi_file = File(
        desc='path/name of fiber track tract density image file (if generated)')
    tdi2_file = File(
        desc='path/name of fiber track tract density image file in subvoxel '
             'diffusion space (if generated)')
    tdi_color_file = File(
        desc='path/name of fiber track tract color density image file '
             '(if generated)')
    tdi_end_file = File(
        desc='path/name of fiber track tract density image endpoints file '
             '(if generated)')
    tdi2_end_file = File(
        desc='path/name of fiber track tract density image endpoints in '
             'subvoxel diffusion space file (if generated')
    fa_file = File(
        desc='path/name of along tract fa values file (if generated)')
    gfa_file = File(
        desc='path/name of along tract gfa values file (if generated)')
    qa_file = File(
        desc='path/name of along tract qa values file (if generated)')
    nqa_file = File(
        desc='path/name of along tract nqa values file (if generated)')
    md_file = File(
        desc='path/name of along tract md values file (if generated)')
    ad_file = File(
        desc='path/name of along tract ad values file (if generated)')
    rd_file = File(
        desc='path/name of along tract rd values file (if generated)')
    report_fa_file = File(
        desc='path/name of tract report fa values file (if generated)')
    report_gfa_file = File(
        desc='path/name of tract report gfa values file (if generated)')
    report_qa_file = File(
        desc='path/name of tract report qa values file (if generated)')
    report_nqa_file = File(
        desc='path/name of tract report nqa values file (if generated)')
    report_md_file = File(
        desc='path/name of tract report md values file (if generated)')
    report_ad_file = File(
        desc='path/name of tract report ad values file (if generated)')
    report_rd_file = File(
        desc='path/name of tract report rd values file (if generated)')


class DSIStudioFiberCommand(DSIStudioCommand):
    """Not used directly, provides region and post-processing commands for
    DSI Studio trk and ana actions.
    """
    input_spec = DSIStudioFiberInputSpec
    
    def __init__(self, **inputs):
        super(DSIStudioFiberCommand, self).__init__(**inputs)
        self.inputs.on_trait_change(self._report_update, 'report+')
        self.inputs.on_trait_change(self._export_update, 'export+,report')

        self._output_pfx = None
        self._output_basename = None

    def _gen_output_pfx_base(self):
        def get_attr_or_undefined(inputs, name):
            try:
                attr = getattr(inputs, name)
            except AttributeError:
                attr = _Undefined()
            return attr
        source_val = get_attr_or_undefined(self.inputs, 'source')
        tract_name = get_attr_or_undefined(self.inputs, 'tract_name')
        tract_val = get_attr_or_undefined(self.inputs, 'tract')
        pfx = self._output_pfx

        if isdefined(tract_val):
            self._output_pfx = None  # tract_name assumed to be in tract_val
            _, self._output_basename, _ = split_filename(
                os.path.abspath(tract_val))
        elif isdefined(source_val):
            if isdefined(tract_name):
                self._output_pfx = ''.join((tract_name, '_'))
                _, self._output_basename, _ = split_filename(
                    os.path.abspath(source_val))
            elif pfx is None or not pfx.startswith('Track_'):
                self._output_pfx = ('Track_{:04d}{:02d}{:02d}_{:02d}{:02d}{:02d}_'
                                    .format(*time.localtime(time.time())))
                _, self._output_basename, _ = split_filename(
                    os.path.abspath(source_val))
        else:
            self._output_pfx = None
            self._output_basename = None

    def _gen_filename(self, name):
        """Executed if self.inputs.name is undefined, but genfile=True"""
        fname = []
        fname.extend((
            self._output_pfx,
            self._output_basename))
        suffix = DSIInfo.ot_to_ext(self.inputs.output_type)
        if name == 'output':
            suffix = None
            ext = DSIInfo.ot_to_ext(self.inputs.output_type)
        elif name == 'endpt':
            suffix = '_endpt'
            ext = self.inputs.endpt_format
        elif name.endswith('_file'):
            export = name.replace('_file', '')
            if export in DSIInfo.export_texts:
                ext = ''.join(('.', export, '.txt'))
            elif export in DSIInfo.exprot_imgs:
                ext = ''.join(('.', export, '.nii'))
            elif export in DSIInfo.report_texts:
                rp = str(getattr(self.inputs, 'report_pstyle'))
                rb = str(getattr(self.inputs, 'report_bandwidth'))
                suffix = '.'.join((
                    DSIInfo.ot_to_ext(self.inputs.output_type),
                    export.replace('_', '.'), rp, rb))
                ext = '.txt'
        else:
            raise NotImplementedError
        return self._gen_fname(''.join([item for item in fname if item is not None]),
                               change_ext=True,
                               suffix=suffix,
                               ext=ext)
    
    def _regions_update(self):
        """Update region category ('rois', 'roas', etc.) with atlas regions"""
        regions = ('rois', 'roas', 'ends', 'seed', 'ter')
        for name in regions:
            value = getattr(self.inputs, name)
            spec = self.inputs.trait(name)
            argstr = spec.argstr
            sep = spec.sep
            
            # --roi=1 --roi2=2 --roi3=3, same pattern for all regions
            arglist = []
            if not isdefined(value):
                value = []
                
            # change seed and ter values to 1-Lists for loop, others are
            # automatically changed by MultiPath due to InputSpec
            if not isinstance(value, list):
                value = [value]

            # Get values for name_ar
            trait_name_ar_list = []  # atlas regions
            trait_name_ar_list.extend((name, '_ar'))
            trait_name_ar = ''.join(trait_name_ar_list)
            region_names = getattr(self.inputs, trait_name_ar)
            if not isdefined(region_names):
                region_names = []
            
            # Get values for name_atlas
            trait_name_atlas_list = []
            trait_name_atlas_list.extend((name, '_atlas'))
            trait_name_atlas = ''.join(trait_name_atlas_list)
            atlas_names = getattr(self.inputs, trait_name_atlas)
            if not isdefined(atlas_names):
                atlas_names = []

            # Update
            # File exists check is in InputSpec, so atlas must be in
            # dsistudio_directory/atlas
            if len(atlas_names) != 0:
                if len(region_names) == len(atlas_names):
                    for i in range(0, len(atlas_names)):
                        atlas = atlas_names[i]
                        update = list_to_str(
                            sep='',
                            args=(os.environ['DSIDIR'],
                                  '/atlas/',
                                  atlas,
                                  '.nii.gz'))
                        # check we haven't already updated
                        # True if updated, or more file regions included
                        if len(value) >= len(atlas_names):
                            # True if not updated
                            if value[len(value)-len(atlas_names)+i] != update:
                                value.append(update)
                                setattr(self.inputs, name, value)
                                print('Appended atlas: {} to {}'
                                      .format(atlas, name))
                        else:
                            value.append(update)
                            setattr(self.inputs, name, value)
                            print('Appended atlas: {} to {}'
                                  .format(atlas, name))
                else:
                    raise AttributeError('N entries in {} must equal '
                                         'N entries in {}'
                                         .format(trait_name_ar, trait_name_atlas))
                        
    def _report_update(self):
        """Update report, report_val from related boolean traits"""
        name = 'report'
        secname = 'report_val'
        thisbool = getattr(self.inputs, name)
        default_values = self.inputs.trait(secname).get_validate()[1]
        if default_values is not None:
            subbools = [getattr(self.inputs, '_'.join((name, e)))
                        for e in default_values]
            sbc = subbools.count(True)
            if sbc > 1:
                raise(StandardError(
                    'May only output one report, but {} True'
                    .format(['_'.join((name, el)) for el in
                             tuple(compress(default_values, subbools))
                             ])
                ))
            elif sbc == 1:
                setattr(self.inputs, name, True)
                setattr(self.inputs, secname, 
                        default_values[subbools.index(True)])
            elif sbc == 0:
                setattr(self.inputs, name, _Undefined())
                setattr(self.inputs, secname, _Undefined())

    def _export_update(self):
        """Update export from related traits"""
        name = 'export'
        values = getattr(self.inputs, name)
        if not isdefined(values):
            values = []
        default_traits = DSIInfo.export_values
        
        newvalues = []
        for e in default_traits:
            subbool = getattr(self.inputs, e)
            if isdefined(subbool) and subbool:
                newvalues.append(e.replace('export_', ''))
        if len(newvalues) > 0:
            setattr(self.inputs, name, newvalues)
        else:
            setattr(self.inputs, name, _Undefined())

    def _check_mandatory_inputs(self):
        """correct values, then call super"""
        # trait change notifiers don't seem to fire when traits updated on
        # instantiation. Make sure all values are validated before gen cmdline
        self._update_from_indict()
        self._report_update()
        self._export_update()
        self._gen_output_pfx_base()
                    
        super(DSIStudioFiberCommand, self)._check_mandatory_inputs()

    def _add_atlas_regions(self, name, value):
        """helper function for _format_arg,
        will add atlas regions to atlas file paths
        
        Parameters
        ----------
        name    : str (input name, e.g. 'seed','rois','roas','ends','ter')
        value   : list(str) (paths or atlas regions, all together for name)
        
        Returns
        -------
        newval  : list(str) (atlas with appended :regionname, or path to other)
        """
        trait_name_ar_list = []
        trait_name_ar_list.extend((name, '_ar'))
        trait_name_ar = ''.join(trait_name_ar_list)
        region_names = getattr(self.inputs, trait_name_ar)  # matching atlas regions
        
        trait_name_atlas_list = []
        trait_name_atlas_list.extend((name, '_atlas'))
        trait_name_atlas = ''.join(trait_name_atlas_list)
        atlas_name = getattr(self.inputs, trait_name_atlas)  # matching atlas

        if not isdefined(region_names):
            return value  # return input if no atlas regions
        else:
            newvalue = []
            newvalue.extend(value) 
            # newvalue = value would lead to checking for file exists, it won't
            if len(region_names) != len(atlas_name):
                raise AttributeError('len( {} ) must equal len( {} )'
                                     .format(trait_name_ar, trait_name_atlas))
            for i in range(0, len(region_names)):
                atlas = newvalue[len(value)-len(region_names)+i]
                ar = region_names[i]
                newval_list = []
                newval_list.extend((atlas, ':', ar))
                newvalue[len(value)-len(region_names)+i] = ''.join(newval_list)
            return newvalue

    def _add_region_actions(self, name, value):
        """helper function for _format_arg, 
        will add region action inputs to input value
        
        Parameters
        ----------
        name    : str (input name, e.g. 'seed','rois','roas','ends','ter')
        value   : list(str) (paths or atlas regions, all together for name)
        
        Returns
        -------
        newval  : list(str) (region name or paths, with appended action options)

        Example
        -------
        trk=Node(interface=DSIStudioTrack())
        trk.inputs.roi=['ROI1.nii','ROI2.nii']
        trk.inputs.roi_actions=[['dilation'],['dilation','smoothing']]
        trk.inputs.cmdline
        'dsi_studio --action=trk --roi=ROI1.nii,dilation \
        --roi2=ROI2.nii,dilation,smoothing'
        """
        
        trait_name_actions_list = []
        trait_name_actions_list.extend((name, '_actions'))
        trait_name_actions = ''.join(trait_name_actions_list)
        actions = getattr(self.inputs, trait_name_actions)  # matching action values
        actions_ts = self.inputs.trait(trait_name_actions)  # action values traitspec
        
        if isdefined(actions) and len(actions) != len(value):
            print('name={}, value={}, actions={}'.format(name, value, actions))
            raise AttributeError('N Entries in {} action list does not match '
                                 'N Regions (Files + Atlas Regions)'.format(name))
        
        if not isdefined(actions):  # if there are no region actions
            return value  # return input
        else:  # if there are region actions
            newvalue = []
            for i in range(0, len(actions)):
                oldval = value[i]
                acts = actions[i]
                if isdefined(actions_ts.sep):
                    sep = actions_ts.sep
                else:
                    sep = ','
                    
                modval = []
                modval.append(oldval)
                
                if acts:  # if not an empty list
                    modval.append(''.join(
                        (sep, list_to_str(sep=sep, args=[elt for elt in acts]))
                    ))
                newvalue.append(''.join(modval))
            return newvalue

    def _format_arg(self, name, trait_spec, value):
        """alternative helper function for _parse_inputs, 
        format rois, roas, ends, seed, ter, export, atlas argstrs
        will not change input, only how it's interpreted
        
        Parameters
        ----------
        name        :   str (input name, from DSIStudioFiberInputSpec)
        trait_spec  :   trait_spec (input trait_spec from DSIStudioFiberInputSpec)
        value       :   variable type (input command value)
        
        Returns
        -------
        argstr with value replacing %type in input argstr
        """

        argstr = trait_spec.argstr
        sep = trait_spec.sep if trait_spec.sep is not None else ' '
        returnstr = None

        if name == 'rois' or \
           name == 'roas' or \
           name == 'ends' or \
           name == 'seed' or \
           name == 'ter':
            # --roi=1 --roi2=2 --roi3=3, same pattern for all regions
            arglist = []
            if not isdefined(value):
                value = []
                
            # change seed and ter values to 1-Lists for loop, others are
            # automatically changed by MultiPath due to InputSpec
            if not isinstance(value, list):
                value = [value]
            
            # add atlas regions if available, can't add before bcz it
            # wouldn't validate as a file
            # value now includes atlas if it is an input
            value_with_atlas_regions = self._add_atlas_regions(name, value)
            correct_value = self._add_region_actions(name, value_with_atlas_regions)

            # add roi number labels as needed
            for i in range(0, len(value)):
                if i == 0:
                    roin = ''
                elif (name == 'rois' or 
                      name == 'roas' or 
                      name == 'ter') and i > 4:
                    print('Cannot have more than 5 {}, first 5 used.\n'
                          '{} not included'
                          .format(name, ', '.join(value[x] for x in range(i, len(value)))))
                    break
                elif name == 'ends' and i > 1:
                    print('Cannot have more than 2 ends, first 2 used.\n'
                          '{} not included'
                          .format(', '.join(value[x] for x in range(i, len(value)))))
                    break
                else:
                    roin = i + 1
                    
                arglist.append(argstr % (roin, correct_value[i]))
                
            returnstr = sep.join(arglist)
            
        elif name == 'export': 
            for e in value:
                if e == 'report':
                    if (isdefined(self.inputs.report_val) and
                       isdefined(self.inputs.report_pstyle) and
                       isdefined(self.inputs.report_bandwidth)):
                        newe = []
                        newe.extend(
                            (e,
                             self.inputs.report_val,
                             str(self.inputs.report_pstyle),
                             str(self.inputs.report_bandwidth)))
                        i = value.index(e)
                        report_sep = self.inputs.trait('report').sep
                        value[i] = report_sep.join(newe)
                    else:
                        raise AttributeError(
                            'Export report requested, but not all '
                            'required fields: ("report_val", "report_pstyle", '
                            '"report_bandwidth") have been set')
            returnstr = argstr % sep.join(str(e) for e in value)
            
        elif name == 'connectivity':
            if not isdefined(value):
                value = []
                
            conn_type = getattr(self.inputs, 'connectivity_type')
            conn_value = getattr(self.inputs, 'connectivity_value')
            conn_atlas = getattr(self.inputs, 'connectivity_atlas')
            if isdefined(conn_atlas):
                value.extend(conn_atlas)
            if len(value) == len(conn_type) and len(value) == len(conn_value):
                return super(DSIStudioFiberCommand, self)._format_arg(
                    name, trait_spec, value)
            else:
                raise IndexError('N inputs for connectivity, connectivity_'
                                 'type, connectivity_value must be equal')
        
        elif name == 'cluster':
            returnstr = argstr % (
                getattr(self.inputs, 'cluster_method_id'),
                getattr(self.inputs, 'cluster_count'),
                getattr(self.inputs, 'cluster_res'),
                getattr(self.inputs, 'cluster_output_fname'))
        
        else:
            return super(DSIStudioFiberCommand, self)._format_arg(
                name, trait_spec, value)
            
        return returnstr

    def _parse_inputs(self, skip=None):
        deftoskip = ('report_val',
                     'report_pstyle',
                     'report_bandwidth')
        if skip is None:
            toskip = deftoskip
        else:
            toskip = []
            toskip.extend(skip)
            toskip.extend(deftoskip)
        return super(DSIStudioFiberCommand, self)._parse_inputs(skip=toskip)
        
    def _list_outputs(self):
        outputs = self._outputs().get()
        for key in outputs.iterkeys():
            basekey = key.replace('_file', '')
            if key == 'output':
                outputs['output'] = self._gen_filename('output')
            # the following are booleans
            elif (key == 'endpt' and
                  isdefined(getattr(self.inputs, 'endpt')) and
                  getattr(self.inputs, 'endpt')):
                outputs['endpt'] = self._gen_fname(
                    self._gen_filename('output'),
                    suffix='_endpt',
                    change_ext=True,
                    ext=self.inputs.endpt_format)

            elif basekey in DSIInfo.export_texts:
                inputkey = '_'.join(('export', basekey))
                if (isdefined(getattr(self.inputs, inputkey)) and
                   getattr(self.inputs, inputkey)):
                        outputs[key] = self._gen_fname(
                            self._gen_filename('output'),
                            suffix='.'.join((
                                DSIInfo.ot_to_ext(self.inputs.output_type),
                                basekey)),
                            change_ext=True,
                            ext='.txt')
                        
            elif basekey in DSIInfo.export_imgs:
                inputkey = '_'.join(('export', basekey))
                if (isdefined(getattr(self.inputs, inputkey)) and
                    getattr(self.inputs, inputkey)):
                        outputs[key] = self._gen_fname(
                            self._gen_filename('output'),
                            suffix='.'.join((
                                DSIInfo.ot_to_ext(self.inputs.output_type),
                                basekey)),
                            change_ext=True,
                            ext='.nii')
                    
            elif (basekey in DSIInfo.report_texts and
                  isdefined(getattr(self.inputs, basekey)) and
                  getattr(self.inputs, basekey)):
                rp = str(getattr(self.inputs, 'report_pstyle'))
                rb = str(getattr(self.inputs, 'report_bandwidth'))
                outputs[key] = self._gen_fname(
                    self._gen_filename('output'),
                    suffix='.'.join((
                        DSIInfo.ot_to_ext(self.inputs.output_type),
                        basekey.replace('_', '.'), rp, rb)),
                    change_ext=True,
                    ext='.txt')
        return outputs


class DSIStudioTrackInputSpec(DSIStudioFiberInputSpec):
    """Input specification for DSI Studio fiber tracking"""

    output_type = traits.Enum(
        'TRK', 'TXT', 'NIFTI',
        usedefault=True,
        desc='DSI Studio trk action output type')
    method = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--method=%d',
        desc='0:streamline (default), 1:rk4')
    fiber_count = traits.Int(
        5000,
        argstr='--fiber_count=%d',
        desc='number of fiber tracks to find, end criterion')
    seed_count = traits.Int(
        10000000,
        argstr='--seed_count=%d',
        desc='max number of seeds, end criterion')
    otsu_threshold = traits.Float(
        0.6,
        argstr='--otsu_threshold=%.4f',
        desc='Otsu threshold ratio, default 0.6, will not apply if fa '
             'threshold specified')
    fa_threshold = traits.Float(
        0.1,
        argstr='--fa_threshold=%.4f',
        position=4,
        desc='fa theshold or qa threshold depending on rec method')
    dt_threshold = traits.Float(
        0.0,
        argstr='--dt_threshold=%.4f',
        desc='percent change')
    threshold_index = traits.Str(
        argstr='--threshold_index=%s',
        requires=['fa_threshold'], 
        desc='assign threshold to another index')
    initial_dir = traits.Enum(
        0, 1, 2,
        argstr='--initial_dir=%d',
        desc='initial propagation direction, 0:primary fiber (default),'
             '1:random, 2:all fiber orientations')
    interpolation = traits.Enum(
        0, 1, 2,
        argstr='--interpolation=%d',
        desc='interpolation method, 0:trilinear, 1:gaussian radial, '
             '2:nearest neighbor')
    seed_plan = traits.Enum(
        0, 1,
        argstr='--seed_plan=%d',
        desc='seeding strategy, 0:subvoxel random(default), 1:voxelwise center')
    random_seed = traits.Enum(
        0, 1,
        argstr='--random_seed=%d',
        desc='whether a timer is used to generate seed points, default is off')
    check_ending = traits.Enum(
        0, 1,
        argstr='--check_ending=%d',
        desc='whether to check streamline endings, default is off')
    tip_iteration = traits.Int(
        0,
        argstr='--tip_iteration=%d',
        desc='number of iterations for topology informed pruning')
    thread_count = traits.Int(
        2,
        argstr='--thread_count=%d',
        desc='Assign number of threads to use')
    turning_angle = traits.Int(
        60,
        argstr='--turning_angle=%d', 
        position=5,
        desc='degrees incoming tract dir may differ from outgoing in voxel')
    # listed on website, but didn't seem to be in code, and I don't know
    # what it's supposed to do - leaving out should get default regardless
    # interpo_angle = traits.Int(60, argstr='--interpo_angle=%d', desc='')
    step_size = traits.Float(
        1.00,
        usedefault=True, 
        argstr='--step_size=%.2f', 
        position=8,
        desc='moving distance in each tracking interval, default 1 mm')
    smoothing = traits.Float(
        0.00,
        usedefault=True, 
        argstr='--smoothing=%.2f', 
        position=9,
        desc='fiber track momentum, default disabled')
    min_length = traits.Int(
        30,
        usedefault=True, 
        argstr='--min_length=%d', 
        position=6,
        desc='tracks below mm length deleted, default 30')
    max_length = traits.Int(
        300,
        usedefault=True, 
        argstr='--max_length=%d', 
        position=7,
        desc='tracks above mm length deleted, default 300')
    parameter_id = traits.Str(
        argstr='--parameter_id=%s',
        desc='set all parameters together with string found in GUI method text')


class DSIStudioTrack(DSIStudioFiberCommand):
    """DSI Studio fiber tracking action support

    Example
    -------
    trk = DSIStudioTrack()
    trk.inputs.source = 'my.fib.gz'
    trk.inputs.output = 'my.trk.gz'
    trk.inputs.roi = ['myR1.nii.gz','myR2.nii.gz']
    trk.inputs.roa = 'myR3.nii.gz'
    trk.inputs.fa_threshold = 0.1
    trk.inputs.fiber_count = 1000
    trk.inputs.seed_count = 100000
    trk.inputs.method = 0
    trk.inputs.thread_count = 2
    trk.cmdline

    Would output:
    dsi_studio --action=trk --source=my.fib.gz --output=my.trk.gz \
    --roi=myR1.nii.gz --roi2=myR2.nii.gz --roa=myR3.nii.gz --fa_threshold=0.1 \
    --fiber_count=1000 --seed_count=100000 --method=0 --thread_count=2
    """

    _action = 'trk'
    _output_type = 'TRK'
    input_spec = DSIStudioTrackInputSpec
    output_spec = DSIStudioFiberOutputSpec

    def __init__(self, **inputs):
        super(DSIStudioTrack, self).__init__(**inputs)
        self.inputs.on_trait_change(self._gen_output_pfx_base, 'source')


class DSIStudioAnalysisInputSpec(DSIStudioFiberInputSpec):

    output_type = traits.Enum(
        'NIFTI', 'TRK', 'TXT',
        usedefault=True,
        desc='DSI Studio ana action output type')
    roi = InputMultiPath(
        File(exists=True),
        argstr='roi=%s',
        sep=';',
        desc='Text, nifti, or atlas regions for region-based analysis')
    tract = File(
        exists=True,
        argstr='--tract=%s',
        desc='assign tract file for analysis')
    atlas = traits.List(
        traits.Enum(*DSIInfo.atlases),
        argstr='--atlas=%s',
        sep=',',
        desc='atlas name(s) found in dsistudio/build/atlas')


class DSIStudioAnalysis(DSIStudioFiberCommand):
    """DSI Studio analysis action support

    Example
    -------
    ana = DSIStudioAnalysis()
    ana.inputs.source = 'my.fib.gz'
    ana.inputs.tract = 'myTract.trk.gz'
    ana.inputs.output = 'myTract.txt'
    ana.inputs.export = 'stat'
    ana.cmdline

    Would output:
    'dsi_studio --action=ana --source=my.fib.gz --tract=myTract.trk.gz \
    --output=myTract.txt --export=stat'
    """
    _action = 'ana'
    _output_type = 'TXT'
    input_spec = DSIStudioAnalysisInputSpec
    output_spec = DSIStudioFiberOutputSpec

    def __init__(self, **inputs):
        super(DSIStudioAnalysis, self).__init__(**inputs)
        self.inputs.on_trait_change(self._gen_output_pfx_base, 'source,tract')


class DSIStudioSourceInputSpec(DSIStudioInputSpec):
    
    output = File(
        genfile=True,
        argstr='--output=%s',
        hash_files=False,
        desc='assign the output src file path and name',
        position=3)
    output_type = traits.Enum(
        'SRC',
        usedefault=True,
        desc='DSI Studio src action output type')
    b_table = File(
        exists=True,
        argstr='--b_table=%s',
        xor=['bval', 'bvec'],
        desc='assign the replacement b-table')
    bval = File(
        exists=True,
        argstr='--bval=%s',
        xor=['b_table'],
        desc='assign the b value text file')
    bvec = File(
        exists=True,
        argstr='--bvec=%s',
        xor=['b_table'],
        desc='assign the b vector text file')
    recursive = traits.Enum(
        0, 1,
        argstr='--recursive=%d',
        desc='whether to search files in subdirectories')


class DSIStudioSourceOutputSpec(DSIStudioOutputSpec):
    
    output = File(
        exists=False,
        desc='DSI Studio src file')


class DSIStudioSource(DSIStudioCommand):
    """DSI Studio SRC action support
    
    Example
    -------
    
    from DINGO.DSI_Studio_base import DSIStudioSource
    src = DSIStudioSource()
    src.inputs.source = 'mydti.nii.gz'
    src.inputs.bval = 'mybval.bval'
    src.inputs.bvec = 'mybvec.bvec'
    src.cmdline
    'dsistudio --action=src --source=mydti.nii.gz --output=mydti.src.gz \
    --bval=mybval.bval --bvec=mybvec.bvec
    """
    _action = 'src'
    _output_type = 'SRC'
    input_spec = DSIStudioSourceInputSpec
    output_spec = DSIStudioSourceOutputSpec

    def _gen_filename(self, name):
        if name == 'output':
            out = self.inputs.output
            if not isdefined(out) and isdefined(self.inputs.source):
                out = self._gen_fname(self.inputs.source, change_ext=True)
                working_dir = os.getcwd()  # present cache working dir
                outbase = os.path.basename(out)
                out = os.path.join(working_dir, outbase)
            return os.path.abspath(out)
        else:
            return super(DSIStudioSource, self)._gen_filename(name)
            
    def _list_outputs(self):
        outputs = self._outputs().get()
        
        outputs['output'] = self._gen_filename('output')
        return outputs
        
    def _check_mandatory_inputs(self):
        """Update other inputs from inputs.indict then call super"""
        self._update_from_indict()
        super(DSIStudioSource, self)._check_mandatory_inputs()


class DSIStudioReconstructInputSpec(DSIStudioInputSpec):
    
    thread_count = traits.Int(
        1,
        argstr='--thread_count=%d',
        desc='Number of threads to use for reconstruction')
    mask = File(
        exists=True,
        argstr='--mask=%s',
        desc='assign a nifti format mask')
    output_type = traits.Enum(
        'FIB',
        usedefault=True,
        desc='DSI Studio rec action output type')
                            
    method = traits.Enum(
        'dti', 'dsi', 'frqbi', 'shqbi', 'gqi', 'hardi', 'qsdr',
        mandatory=True, 
        argstr='--method=%d',
        desc='Reconstruction method, DSI:0, DTI:1, Funk-Randon QBI:2, '
             'Spherical Harmonic QBI:3, GQI:4, Convert to HARDI:6, QSDR:7')

    # params includes some floats, some ints depending on method, but dsi studio
    # actually reads them all as floats, so should be fine here
    param = traits.List(
        traits.Float(),
        argstr='--param%s=%s',
        desc='Reconstruction parameters, different meaning and types for '
             'different methods')
    
    affine = File(
        exists=True,
        argstr='--affine=%s',
        desc='text file containing a transformation matrix. e.g. the following '
             'shifts in x and y by 10 voxels: \n1 0 0 -10 \n 0 1 0 -10 \n 0 0 1 0')
    flip = traits.Int(
        argstr='--flip=%d', 
        desc='flip image volume and b-table. 0:flip x, 1:flip y, 2:flip z, '
             '3:flip xy, 4:flip yz, 5: flip xz. \n'
             'e.g. 301 performs flip xy, flip x, flip y')
    motion_corr = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--motion_correction=%d',
        desc='whether to apply motion and eddy correction, only DTI dataset')
    check_btable = traits.Enum(
        1, 0,
        usedefault=True,
        argstr='--check_btable=%d',
        desc='whether to do b-table flipping, default yes')
    hanning_filter_width = traits.Int(
        16,
        usedefault=True,
        desc='DSI - Hanning filter width')
    output_dif = traits.Enum(
        1, 0,
        usedefault=True,
        argstr='--output_dif=%d',
        desc='DTI - output diffusivity, default 1')
    output_tensor = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--output_tensor=%d',
        desc='DTI - output whole tensor, default 0')
    smooth_kernel_width = traits.Int(
        15,
        usedefault=True,
        desc='FRQBI - width of gaussian smoothing kernel')
    interp_kernel_width = traits.Int(
        5,
        usedefault=True,
        desc='FRQBI - width of interpolation kernel')
    odf_order = traits.Enum(
        8, 4, 5, 6, 10, 12, 16, 20,
        usedefault=True,
        argstr='--odf_order=%d',
        desc='FRQBI,SHQBI,GQI,QSDR - tesselation number of the odf, default 8')
    record_odf = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--record_odf=%d',
        desc='FRQBI,SHQBI,GQI,QSDR - whether to output ODF for connectometry '
             'analysis')
    regularization = traits.Float(
        0.006,
        desc='FRQBI,SHQBI,GQI,QSDR - regularization parameter')
    harmonic_order = traits.Int(
        8,
        usedefault=True,
        desc='SHQBI - order of spherical harmonics')
    mddr = traits.Float(
        1.25,
        usedefault=True,
        desc='GQI - ratio of the mean diffusion distance')
    r2_weighted = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--r2_weighted=%d',
        desc='GQI - whether to apply r2 weighted reconstruction')
    output_rdi = traits.Enum(
        1, 0,
        usedefault=True,
        argstr='--output_rdi=%d',
        desc='GQI,QSDR - output restricted diffusion imaging, default 1')
    csf_cal = traits.Enum(
        1, 0,
        usedefault=True,
        argstr='--csf_calibration=%d',
        desc='GQI,QSDR - enable CSF calibration, default 1')
    b_value = traits.Int(
        3000,
        usedefault=True,
        desc='HARDI - b-value')
    output_resolution = traits.Float(
        2,
        usedefault=True,
        desc='QSDR - output resolution in mm')
    # --other_image=t1w,/directory/my_t1w.nii.gz;t2w,/directory/my_t1w.nii.gz
    other_image = traits.Bool(
        argstr='--other_image=%s,%s',
        sep=';',
        requires=['other_image_type', 'other_image_file'],
        desc='QSDR - whether to wrap other image volumes')
    other_image_type = traits.List(
        traits.Enum('t1w', 't2w'),
        requires=['other_image', 'other_image_file'],
        desc='QSDR - t1w or t2w (maybe others, but unsure,unimplemented)')
    other_image_file = InputMultiPath(
        File(exists=True),
        requires=['other_image', 'other_image_type'],
        desc='QSDR - filepath for image to be wrapped')
    output_mapping = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--output_mapping=%d',
        desc='QSDR - output mapping for each voxel, default 0')
    output_jac = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--output_jac=%d',
        desc='QSDR - output jacobian determinant, default 0')
    interpolation = traits.Enum(
        0, 1, 2,
        usedefault=True,
        argstr='--interpolation=%d',  # says interpo_method in docs, but not code
        desc='QSDR - interpolation method, 0:trilinear (default), '
             '1:gaussian radial basis, 2:tricubic')
    num_fiber = traits.Int(
        5,
        usedefault=True,
        argstr='--num_fiber=%d',
        desc='FRQBI,SHQBI,GQI,QSDR - max count of resolving fibers per voxel, '
             'default 5')
    scheme_balance = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--scheme_balance=%d',
        desc='0:disable scheme balance, 1:enable scheme balance')
    half_sphere = traits.Enum(
        0, 1,
        usedefault=True,
        argstr='--half_sphere=%d',
        desc='whether data acquired with half sphere DSI')
    deconvolution = traits.Enum(
        0, 1,
        argstr='--deconvolution=%d --param2=%.4f',
        desc='whether to apply deconvolution, requires regularization')
    decomposition = traits.Enum(
        0, 1,
        argstr='--decomposition=%d --param3=%.4f --param4=%d',
        desc='whether to apply decomposition, requires decomp_frac, m_value')
    decomp_frac = traits.Float(
        0.05,
        requires=['decomposition'],
        desc='decomposition fraction')
    m_value = traits.Int(
        10,
        requires=['decomposition'],
        desc='decomposition m value')
    regist_method = traits.Enum(
        0, 1, 2, 3, 4,
        usedefault=True,
        argstr='--reg_method=%d',
        desc='QSDR - registration method 0:SPM 7-9-7, 1:SPM 14-18-14, '
             '2:SPM 21-27-21, 3:CDM, 4:T1W-CDM')
    t1w = File(
        exists=True,
        argstr='--t1w=%s', 
        requires=['regist_method'],
        desc='QSDR - assign a t1w file for registration method 4')
    template = File(
        exists=True,
        argstr='--template=%s',
        desc='QSDR - assign a template file for spatial normalization')


class DSIStudioReconstructOutputSpec(DSIStudioOutputSpec):
    """DSI Studio reconstruct output specification"""
    fiber_file = File(exists=True, desc='Fiber tracking file')
# filename depends on reconstruction method, and automatic detections by
# DSIStudio, actual output file acquired from runtime
# Decoding the file extension
# The FIB file generated during the reconstruction will include several extension
# Here is a list of the explanation
# odf8: An 8-fold ODF tessellation was used
# f5: For each voxel, a maximum of 5 fiber directions were resolved
# rec: ODF information was output in the FIB file
# csfc: quantitative diffusion MRI was conducted using CSF location as the free
    # water calibration
# hs: A half sphere scheme was used to acquired DSI
# reg0i2: the spatial normalization was conducted using
# (reg0: 7-9-7 reg1: 14-18-14 reg2: 21-27-21) and the images were interpolated
# using (i0: trilinear interpolation, I1: Guassian radial basis i2: cubic spine)
# bal: The diffusion scheme was resampled to ensure balance in the 3D space
    # fx, fy, fz: The b-table was automatically flipped by DSI Studio in
    # x-, y-, or z- direction. 012 means the order of the x-y-z coordinates is
    # the same, whereas 102 indicates x-y flip, 210 x-z flip, and 021 y-z- flip.
# rdi: The restricted diffusioin imaging metrics were calculated
# de: deconvolution was used to sharpen the ODF
# dec: decomposition was used to sharpen the ODF
# dti: The images were reconstructed using diffusion tensor imaging
# gqi: The images were reconstructed using generalized q-sampling imaging
# qsdr: The images were reconstructed using q-space diffeomorphic reconstruction
# R72: The goodness-of-fit between the subject's data and the template has a
    # R-squared value of 0.72


class DSIStudioReconstruct(DSIStudioCommand):
    """DSI Studio reconstruct action support
    """
    _action = 'rec'
    _output_type = 'FIB'
    input_spec = DSIStudioReconstructInputSpec
    output_spec = DSIStudioReconstructOutputSpec
    # terminal_output = 'stream'
    
    def __init__(self, **inputs):
        super(DSIStudioReconstruct, self).__init__(**inputs)
        self.inputs.on_trait_change(self._method_update, 'method')
        
    def _subparam_update(self, name, subparams):
        val = getattr(self.inputs, name)
        spec = self.inputs.trait(name)
        if not isdefined(val) or val == 0:
            setattr(spec, 'requires', None)
        elif val == 1:
            setattr(spec, 'requires', list(subparams))
                
    def _param_update(self):
        name = 'param'
        value = getattr(self.inputs, name)
        spec = self.inputs.trait(name)        
        
        self._subparam_update('deconvolution', ('regularization',))
        self._subparam_update('decomposition', ('decomp_frac', 'm_value'))    
        
        mval = getattr(self.inputs, 'method')
        if isdefined(mval):
            # update param values, requires, and mandatory flag based on method
            param_sources = DSIInfo.rec_mid_to_pids(mval)
            requires = getattr(spec, 'requires')
            if requires is None:
                requires = []
            if len(param_sources) > 0:
                setattr(spec, 'mandatory', True)
                setattr(spec, 'requires', param_sources)
                paramlist = []
                for e in requires:
                    paramval = getattr(self.inputs, e)
                    if isdefined(paramval):
                        paramlist.append(paramval)

                setattr(self.inputs, name, paramlist)
            else:
                setattr(spec, 'mandatory', None)
                setattr(spec, 'requires', None)
                # Defaults are actually to not be a spec attribute, but None
                # should/seems to work the same
                setattr(self.inputs, name, _Undefined())
    
    def _method_update(self):
        name = 'method'
        value = getattr(self.inputs, name)
        spec = self.inputs.trait(name)
        
        if isdefined(value):
            setattr(spec, 'requires', list(DSIInfo.rec_mid_to_req(value)))
        else:
            setattr(spec, 'requires', None)
        
        self._param_update()
            
    def _check_mandatory_inputs(self):
        """using this to insert/update necessary values, then call super
        _check_mandatory_inputs called before any cmd is run
        """
        self._update_from_indict()
        self._method_update()

        # run original _check_mandatory_inputs
        super(DSIStudioReconstruct, self)._check_mandatory_inputs()

    def _format_arg(self, name, trait_spec, value):
        """alternative helper function for _parse_inputs, 
        only include specific argstrs for the reconstruction method,
        format method specific argstrs, params, other_image_...,
        
        Parameters
        ----------
        name        :   str (input spec variable)
        trait_spec  :   trait_spec (self.inputs.name.traits())
        value       :   various (self.inputs.name)
        """

        argstr = trait_spec.argstr
        sep = trait_spec.sep if trait_spec.sep is not None else ' '
        arglist = []
        returnstr = None
        
        if name == 'method':
            # method id to n
            returnstr = argstr % DSIInfo.rec_mid_to_mn(value)
            
        elif name == 'param':
            # method should be defined, parsed in alphabetical order
            reconstruction_method_id = getattr(self.inputs, 'method')
            expparamtypes = DSIInfo.rec_mid_to_ptype(reconstruction_method_id)
            expnparams = len(expparamtypes)
            if reconstruction_method_id == 'DTI':
                pass  # no params
            
            if len(value) == expnparams:
                for e in value:
                    e_idx = value.index(e)
                    arglist.append(argstr % (e_idx, e))

                returnstr = sep.join(arglist)
            else:
                raise AttributeError('N input params: "{:d}" != '
                                     'Expected N params: "{:d}" for Method: {}'
                                     .format(len(value),
                                             expnparams,
                                             reconstruction_method_id))
        
        elif name == 'deconvolution':
            if value == 1:
                regularization = getattr(self.inputs, 'regularization')
                returnstr = argstr % (value, regularization)
            
        elif name == 'decomposition' and value == 1:
            decomp_frac = getattr(self.inputs, 'decomp_frac')
            m_value = getattr(self.inputs, 'm_value')
            returnstr = argstr % (value, decomp_frac, m_value)
            
        # qsdr t1w,t2w image wrapping, check number of inputs match and put
        # values in other_image argstr
        elif name == 'other_image' and value:
            oit = self.inputs.other_image_type
            oif = self.inputs.other_image_file
            _, argstrend = argstr.split('=')
            if len(oit) == len(oif):
                for t in oit:
                    if oit.index(t) == 0:
                        arglist.append(argstr % (t, oif[oit.index(t)]))
                    # in case there are more than 2 options in future
                    elif oit.index(t) < len(oit):
                        arglist.append(argstrend % (t, oif[oit.index(t)]))
                returnstr = sep.join(arglist)
            else:
                raise AttributeError('N other image types != N other image '
                                     'files')
        else:
            return super(DSIStudioReconstruct, self)._format_arg(
                name, trait_spec, value)
        
        return returnstr

    def _parse_inputs(self, skip=None):
        # super._parse_inputs any var with an argstr will be parsed if not a skip
        reconstruction_method_id = getattr(self.inputs, 'method')
        included_params = set(DSIInfo.rec_method_id_inputs[reconstruction_method_id])
        all_params = set().union(*DSIInfo.rec_method_id_inputs.itervalues())
        excluded_params = all_params.difference(included_params)
        deftoskip = []
        for elt in excluded_params:
            deftoskip.append(elt)
        
        if skip is None:
            toskip = deftoskip
        else:
            toskip = []
            deftoskip.extend(skip)
            toskip.extend(deftoskip)
        return super(DSIStudioReconstruct, self)._parse_inputs(skip=toskip)
        
    def aggregate_outputs(self, runtime=None, needed_outputs=None):
        """DSIStudio reconstruct will write the output to the input directory
        with a variable filename, but puts this information in stdout. Copy and 
        fix to write to working directory.
        """
        outputs = self._outputs()
        # as long as terminal_output = 'file' ; stdout in runtime.merged
        if len(runtime.merged) > 0:
            split_output = runtime.merged.split('\n')
        elif len(runtime.stdout) > 0:
            split_output = runtime.stdout.split('\n')
        if 'output data' in split_output and os.path.exists(split_output[-1]):
            afile = split_output[-1]  # last line is created file
            basename = os.path.basename(afile)
            workflow_dir = os.getcwd()  # present cache working directory
            newfile = os.path.join(workflow_dir, basename)
            shutil.move(afile, newfile)
            split_output[-1] = newfile
            runtime.merged = '\n'.join(split_output)
            setattr(outputs, 'fiber_file', newfile)
            return outputs
        raise(IOError('Fiber file not created/found properly for {}.'
                      .format(self.inputs.source)))
    

class DSIStudioAtlasInputSpec(DSIStudioInputSpec):
    cmd = traits.Enum(
        'template', 'db', 'trk', 'roi',
        argstr='--cmd=%s',
        position=3,
        desc='Specify operation to perform. template: average FIB files, '
             'db: create connectometry database, '
             'trk: convert QSDR space track to native space, '
             'roi: convert atlas ROIs to subject space.')
    template = File(
        exists=True,
        argstr='--template=%s',
        desc='used in cmd=db to specify template for creating connectometry db'
             ', use default DSI Studio template if ignored')
    index_name = traits.Enum(
        'sdf', 'iso', 'fa', 'gfa', 'qa', 'nqa', 'md', 'ad', 'rd',
        argstr='--index_name=%s',
        desc='used in cmd=db to specify diffusion metric to extract, '
             'default sdf if ignored')
    atlas = traits.List(
        traits.Enum(*DSIInfo.atlases),
        argstr='--atlas=%s', 
        sep=',',
        desc='used in cmd=roi to specify the name of the atlas to convert')
    tract = File(
        exists=True,
        desc='used in cmd=trk to specify track file for conversion')
    output = traits.Enum(
        'single', 'multiple',
        argstr='--output=%s',
        desc='whether to create one or multiple nifti files')
    output_type = traits.Enum(
        'NIFTI',
        usedefault=True,
        desc='DSI Studio atlas action output type')


class DSIStudioAtlasOutputSpec(DSIStudioOutputSpec):
    output = OutputMultiPath(
        File(exists=True),
        desc='path/name of transformed atlas nifti file(s) '
             '(if generated)')


class DSIStudioAtlas(DSIStudioCommand):
    """DSI Studio atlas action support
    """
    _action = 'atl'
    _output_type = 'NIFTI'
    input_spec = DSIStudioAtlasInputSpec
    
    def __init__(self, **inputs):
        super(DSIStudioAtlas, self).__init__(**inputs)
        self.inputs.on_trait_change(self._cmd_requires_update, 'cmd')
    
    def _cmd_requires_update(self):
        cmdval = getattr(self.inputs, 'cmd')
        cmdspec = self.inputs.trait('cmd')
        
        if isdefined(cmdval):
            if cmdval == 'template':
                setattr(cmdspec, 'requires', None)
            if cmdval == 'db':
                setattr(cmdspec, 'requires', ['template', 'index_name'])
            if cmdval == 'trk':
                setattr(cmdspec, 'requires', ['tract'])
            if cmdval == 'roi':
                setattr(cmdspec, 'requires', ['atlas'])

    def _check_mandatory_inputs(self):
        """Update other inputs from inputs.indict then call super"""
        self._update_from_indict()
        self._cmd_requires_update()
        super(DSIStudioAtlas, self)._check_mandatory_inputs()


class DSIStudioExportInputSpec(DSIStudioInputSpec):
    export = traits.List(
        traits.Str(),
        argstr='--export=%s',
        sep=',',
        desc='name of export target, includes fa0,fa1,gfa,dir0,dir1,'
             'dirs,image0,4dnii, maybe others')
    output_type = traits.Enum(
        'NIFTI',
        usedefault=True,
        desc='DSI Studio Export output type')


class DSIStudioExportOutputSpec(DSIStudioOutputSpec):
    export = OutputMultiPath(
        File(exists=True),
        desc='matrix information output as nifti files')


class DSIStudioExport(DSIStudioCommand):
    """DSI Studio export action support for exporting matrix information
    """
    _action = 'exp'
    _output_type = 'NIFTI'
    input_spec = DSIStudioExportInputSpec
    output_spec = DSIStudioExportOutputSpec
        
    def aggregate_outputs(self, runtime=None, needed_outputs=None):
        """DSIStudio export will write the output to the input directory
        with a variable filename, but puts this information in stdout.
        """
        outputs = self._outputs()
        outputkey = 'export'
        # as long as terminal_output = 'file' ; stdout in runtime.merged
        if len(runtime.merged) > 0:
            log = runtime.merged
        elif len(runtime.stdout) > 0:
            log = runtime.stdout
        split_stdout = log.split('\n')
        str2find = 'write to file '
        workflow_dir = os.getcwd()
        fixed_outputs = []
        for i in xrange(len(split_stdout)):
            if str2find in split_stdout[i]:
                afile = split_stdout[i].replace(str2find, '')
                basename = os.path.basename(afile)
                newfile = os.path.join(workflow_dir, basename)
                shutil.move(afile, newfile)
                split_stdout[i] = ''.join((str2find, newfile))
                fixed_outputs.append(newfile)
        if len(runtime.merged) > 0:
            runtime.merged = '\n'.join(split_stdout)
        elif len(runtime.stdout) > 0:
            runtime.stdout = '\n'.join(split_stdout)
        n_expected = len(getattr(self.inputs, outputkey))
        if len(fixed_outputs) == n_expected:
            setattr(outputs, outputkey, fixed_outputs)
            return outputs
        else:
            raise(IOError('Export not created/found properly for {}.'
                          .format(self.inputs.source)))
        
    def _check_mandatory_inputs(self):
        """Update other inputs from inputs.indict then call super"""
        self._update_from_indict()
        super(DSIStudioExport, self)._check_mandatory_inputs()
