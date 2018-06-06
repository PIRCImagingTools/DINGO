from nipype.interfaces.base import (traits, File, Directory, InputMultiPath, 
									OutputMultiPath,isdefined, 
									CommandLine, CommandLineInputSpec, 
									TraitedSpec)
import os
from nipype.utils.filemanip import fname_presuffix, split_filename
from traits.trait_base import _Undefined
from traits.api import Trait
from DINGO.utils import list_to_str

import pdb

#copied from nipype.interfaces.base.core 
#with additional imports for debugging purposes
def run_command(runtime, output=None, timeout=0.01):
    """Run a command, read stdout and stderr, prefix with timestamp.

    The returned runtime contains a merged stdout+stderr log with timestamps
    """
    from nipype.utils.filemanip import (read_stream, 
										canonicalize_env as _canonicalize_env)
    from nipype.interfaces.base.support import Stream
    from nipype import logging
    import subprocess as sp
    import select
    import errno
    import gc
    iflogger = logging.getLogger('interface')

	#Start of original
    # Init variables
    cmdline = runtime.cmdline
    env = _canonicalize_env(runtime.environ)

    errfile = None
    outfile = None
    stdout = sp.PIPE
    stderr = sp.PIPE

    if output == 'file':
        outfile = os.path.join(runtime.cwd, 'output.nipype')
        stdout = open(outfile, 'wb')  # t=='text'===default
        stderr = sp.STDOUT
    elif output == 'file_split':
        outfile = os.path.join(runtime.cwd, 'stdout.nipype')
        stdout = open(outfile, 'wb')
        errfile = os.path.join(runtime.cwd, 'stderr.nipype')
        stderr = open(errfile, 'wb')
    elif output == 'file_stdout':
        outfile = os.path.join(runtime.cwd, 'stdout.nipype')
        stdout = open(outfile, 'wb')
    elif output == 'file_stderr':
        errfile = os.path.join(runtime.cwd, 'stderr.nipype')
        stderr = open(errfile, 'wb')

    proc = sp.Popen(
        cmdline,
        stdout=stdout,
        stderr=stderr,
        shell=True,
        cwd=runtime.cwd,
        env=env,
        close_fds=True,
    )

    result = {
        'stdout': [],
        'stderr': [],
        'merged': [],
    }
    #pdb.set_trace()#start of execution
    if output == 'stream':
        streams = [
            Stream('stdout', proc.stdout),
            Stream('stderr', proc.stderr)
        ]

        def _process(drain=0):
            try:
                res = select.select(streams, [], [], timeout)
            except select.error as e:
                iflogger.info(e)
                if e[0] == errno.EINTR:
                    return
                else:
                    raise
            else:
                for stream in res[0]:
                    stream.read(drain)
		
        while proc.returncode is None:
            proc.poll()
            _process()

        _process(drain=1)

        # collect results, merge and return
        result = {}
        temp = []
        for stream in streams:
            rows = stream._rows
            temp += rows
            result[stream._name] = [r[2] for r in rows]
        temp.sort()
        result['merged'] = [r[1] for r in temp]

    if output.startswith('file'):
        proc.wait()
        if outfile is not None:
            stdout.flush()
            stdout.close()
            with open(outfile, 'rb') as ofh:
                stdoutstr = ofh.read()
            result['stdout'] = read_stream(stdoutstr, logger=iflogger)
            del stdoutstr

        if errfile is not None:
            stderr.flush()
            stderr.close()
            with open(errfile, 'rb') as efh:
                stderrstr = efh.read()
            result['stderr'] = read_stream(stderrstr, logger=iflogger)
            del stderrstr

        if output == 'file':
            result['merged'] = result['stdout']
            result['stdout'] = []
    else:
        stdout, stderr = proc.communicate()
        if output == 'allatonce':  # Discard stdout and stderr otherwise
            result['stdout'] = read_stream(stdout, logger=iflogger)
            result['stderr'] = read_stream(stderr, logger=iflogger)

    runtime.returncode = proc.returncode
    try:
        proc.terminate()  # Ensure we are done
    except OSError as error:
        # Python 2 raises when the process is already gone
        if error.errno != errno.ESRCH:
            raise

    # Dereference & force GC for a cleanup
    del proc
    del stdout
    del stderr
    gc.collect()

    runtime.stderr = '\n'.join(result['stderr'])
    runtime.stdout = '\n'.join(result['stdout'])
    runtime.merged = '\n'.join(result['merged'])
    return runtime

class DSIInfo(object):
	#file extensions for output types
	ftypes = {
		'SRC':		'.src.gz',
		'FIB':		'.fib.gz',
		'NIFTI':	'.nii.gz',
		'TRK':		'.trk.gz',
		'TXT':		'.txt'}

	#primary output types for action types
	act_out = {
		'trk': 'TRK',
		'rec': 'FIB',
		'src': 'SRC',
		'ana': 'TXT',
		'atl': 'NIFTI'}

	#reconstruction method id for method number
	rec_method_id_n = {
		'dsi':		0,
		'dti':		1,
		'frqbi':	2,
		'shqbi':	3,
		'gqi':		4,
		'qsdr':		7,
		'hardi':	6}
	
	#reconstruction method param types for method id
	rec_param_types = {
		'dsi':		(int,),
		'dti':		tuple(),
		'frqbi':	(int,int),
		'shqbi':	(float,int),
		'gqi':		(float,),
		'qsdr':		(float,int),
		'hardi':	(float,int,float)}
		
	#reconstruction method param ids for method id
	#order matters method id: (param0, param1, param2)
	rec_param_ids = {
		'dsi':		('hanning_filter_width',),
		'dti':		tuple(),
		'frqbi':	('interp_kernel_width','smooth_kernel_width'),
		'shqbi':	('regularization','harmonic_order'),
		'gqi':		('mddr',),
		'qsdr':		('mddr','output_resolution'),
		'hardi':	('mddr','b_value','regularization')}
				
	#reconstruction method input ids for method id
	#NOT LINKED TO rec_nparams, rec_param_types
	#should include rec_param_ids, but also others, order doesn't matter
	rec_method_id_inputs = {
		'dsi':		('check_btable','hanning_filter_width','deconvolution',
					'decomposition'),
		'dti':		('check_btable','output_dif','output_tensor'),
		'frqbi':	('check_btable','interp_kernel_width','smooth_kernel_width',
					'odf_order','record_odf','num_fiber','deconvolution',
					'decomposition'),
		'shqbi':	('check_btable','harmonic_order','regularization',
					'odf_order','record_odf','num_fiber','deconvolution',
					'decomposition'),
		'gqi':		('check_btable','mddr','r2_weighted','output_rdi',
					'odf_order','record_odf','num_fiber','deconvolution',
					'decomposition'),
		'qsdr':		('check_btable','mddr','r2_weighted',
					'output_resolution','output_mapping','output_jac',
					'output_rdi','odf_order','record_odf','other_image',
					'csf_cal','interpolation','regist_method','num_fiber'),
		'hardi':	('check_btable','mddr','regularization','b_value',
					'num_fiber')}

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
		action : {'src','rec','trk','ana','atl'}
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
		method : {'DSI','DTI','FRQBI','SHQBI','GQI','HARDI','QSDR'}
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
		method : {'DSI','DTI','FRQBI','SHQBI','GQI','HARDI','QSDR'}
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
		method_id	:	Str
		
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

	action = traits.Enum("trk","ana","src","rec","atl","exp","cnt","vis","ren",
		argstr="--action=%s",
		mandatory=True,
		desc="Command action type to execute",
		position=1)
	source = traits.Either(
		File(exists=True),
		Directory(exists=True),
		mandatory=True,
		argstr="--source=%s",
		desc="Input file to process",
		position=2)
	debuglog = File(
		argstr="> %s",
		desc="Log file path/name")
	indict = traits.Dict(
		desc="Dict of keys for inputspec, with their values, will overwrite all"
			" conflicts")



class DSIStudioOutputSpec(TraitedSpec):
	debuglog = File(desc="path/name of log file (if generated)")
	


class DSIStudioCommand(CommandLine):
	"""Base support for DSI Studio commands.
	"""
	_cmd = "dsi_studio"
	_output_type = None
	_action = None
	terminal_output = 'file'

	input_spec = DSIStudioInputSpec

	def __init__(self, **inputs):
		super(DSIStudioCommand, self).__init__(**inputs)
		self.inputs.on_trait_change(self._output_update, 'output_type')
		self.inputs.on_trait_change(self._action_update, 'action')

		if self._action is None:#should be specified in subclass
			raise Exception("Missing action command")

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
					#print("Input: '%s' set to Value: %s" % (key, value))
					#Type checking is handled by traits InputSpec

	def _gen_fname(self, basename, cwd=None, suffix=None, change_ext=True, ext=None):
		"""Generate a filename based on input.
		
		Parameters
		----------
		basename : str (filename to base the new filename)
		cwd : str (path to prefix the new filename)
		suffix : str (suffix to add to the basename)
		change_ext : bool (flag to change the filename extension to
			corresponding output type for action)

		Returns
		-------
		fname : str (new filename based on input)
		"""

		if basename == "":
			raise ValueError("Unable to generate filename for command %s." % (self.cmd))
		if cwd is None:
			cwd = os.getcwd()
		if ext is None:
			ext = DSIInfo.ot_to_ext(self.inputs.output_type)
		if change_ext:
			if suffix:
				suffix = "".join((suffix, ext))
			else:
				suffix = ext
		if suffix is None:
			suffix = ""
		fname = fname_presuffix(basename, suffix=suffix, use_ext=False,
								newpath=cwd)
		return fname
		
	#def _check_mandatory_inputs(self):
		#"""Call super, since executed before command output being used for debugging"""
		#pdb.set_trace()
		#super(DSIStudioCommand, self)._check_mandatory_inputs()
		
				  

class DSIStudioFiberInputSpec(DSIStudioInputSpec):
	"""Provides region and post-processing input
	specification used with DSI Studio trk and ana actions.
	"""
	#ROI Parameters
	seed = File(exists=True,
#DSI Studio has built in accepted values that are not file paths,
#but AtlasName:RegionName
#can't check for atlas ids this way, or lose exists check, so split, but not xor
#		traits.Str(requires=["atlas"]),
		argstr="--seed=%s",
		desc="specify seeding file, txt, analyze, or nifti, unspecified default"
			" is whole brain")
	seed_ar = traits.Str(
		requires=["seed_atlas"],
		desc='seed region in atlas')
	seed_actions = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		sep=",",
		desc="action codes to modify seed region")
	rois = InputMultiPath(File(exists=True), 
		argstr="--roi%s=%s",
		desc="roi through which tracts must pass, txt, analyze, nifti")
	rois_ar = traits.List(traits.Str(),
		requires=["rois_atlas"],
		desc="region in atlas through which tracts must pass")
	rois_actions = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		sep=",",
		desc="action codes to modify rois, list for each roi")
	roas = InputMultiPath(File(exists=True),  
		argstr="--roa%s=%s",
		desc="roa files which tracts must avoid, txt, analyze, nifti")
	roas_ar = traits.List(traits.Str(), 
		requires=["roas_atlas"],
		desc="region in atlas which tracts must avoid")
	roas_actions = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		sep=",",
		desc="action codes to modify roas, list for each roa")
	ends = InputMultiPath(File(exists=True), 
		argstr="--end%s=%s",
		desc="filter out tracks that do not end in this region, txt, analyze, "
			"or nifti")
	ends_ar = traits.List(traits.Str(), 
		requires=["ends_atlas"],
		desc="region in atlas that will filter out tracks that do not end here")
	ends_actions = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		sep=",",
		desc="action codes to modify ends regions, list for each end")
	ter = InputMultiPath(File(exists=True), 
		argstr="--ter=%s",
		desc="terminates any track that enters this region, txt, analyze, "
			"or nifti")
	ter_ar = traits.List(traits.Str(),
		requires=["ter_atlas"],
		desc="region in atlas, terminates any track that enters")
	ter_actions = traits.List(
		traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		sep=",",
		desc="action codes to modify terminative region")
	t1t2 = File(exists=True,
				argstr="--t1t2=%s",
				desc="specify t1w or t2w images as roi reference image")
	seed_atlas = traits.Enum(
		"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
		"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
		"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
		"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
		"talairach","tractography",
		requires=['seed_ar'],
		sep=",",
		desc="atlas name(s) found in dsistudio/build/atlas")
	rois_atlas = traits.List(traits.Enum(
		"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
		"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
		"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
		"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
		"talairach","tractography"),
		requires=['rois_ar'],
		sep=",",
		desc="atlas name(s) found in dsistudio/build/atlas")
	roas_atlas = traits.List(traits.Enum(
		"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
		"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
		"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
		"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
		"talairach","tractography"),
		requires=['roas_ar'],
		sep=",",
		desc="atlas name(s) found in dsistudio/build/atlas")
	ends_atlas = traits.List(traits.Enum(
		"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
		"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
		"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
		"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
		"talairach","tractography"),
		requires=['ends_ar'],
		sep=",",
		desc="atlas name(s) found in dsistudio/build/atlas")
	ter_atlas = traits.List(traits.Enum(
		"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
		"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
		"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
		"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
		"talairach","tractography"),
		requires=['ter_ar'],
		sep=",",
		desc="atlas name(s) found in dsistudio/build/atlas")
	
	#Post-Process Parameters
	delete_repeat = traits.Enum(0,1, 
		argstr="--delete_repeat=%d",
		desc="0 or 1, 1 removes repeat tracks with distance < 1 mm")
		
	output = traits.Either(
		File(genfile=True),
		traits.Enum('no_file'),
		genfile=True,
		argstr="--output=%s",
		hash_files=False,
		desc="output tract file name, format may be txt, trk, or nii",
		position=3)
		
	tract_name = traits.Str(desc='prefix to append to source filename')
		
	endpt = traits.Bool(
		argstr="--end_point=%s",
		requires=['endpt_format'],
		desc="whether to output endpoints file")
		
	endpt_format = traits.Enum('txt','mat',
		usedefault=True,
		desc="endpoint file format, 'txt' or 'mat'")
	
	#separate for later use, inner trait doesn't seem to have values property
	_export_values = ('stat','tdi','tdi2','tdi_color','tdi_end',
		'fa','gfa','qa','nqa','md','ad','rd','report')
	export = traits.List(traits.Enum(*_export_values),
		argstr="--export=%s", 
		sep=',',
		desc="export information related to fiber tracts")
		
	stat = traits.Bool(desc='export statistics along tract or in region')
	tdi = traits.Bool(desc='export tract density image')
	tdi2 = traits.Bool(desc='export tract density image in subvoxel diffusion '
		'space')
	tdi_color = traits.Bool(desc='export tract color density image')
	tdi_end = traits.Bool(desc='export tract density image endpoints')
	tdi2_end = traits.Bool(desc='export tract density image endpoints in '
		'subvoxel diffusion space')
	fa = traits.Bool(desc='export along tract fractional anisotropy values')
	gfa = traits.Bool(desc='export along tract generalized fractional '
		'anisotropy values')
	qa = traits.Bool(desc='export along tract quantitative anisotropy values')
	nqa = traits.Bool(desc='export along tract normalized quantitative '
		'anisotropy values')
	md = traits.Bool(desc='export along tract mean diffusivity values')
	ad = traits.Bool(desc='export along tract axial diffusivity values')
	rd = traits.Bool(desc='export along tract radial diffusivity values')
	
	report = traits.Bool(desc='export tract reports with specified profile '
		'style and bandwidth',
		requires=['report_val','report_pstyle','report_bandwidth'])
	report_val = traits.Enum("fa","gfa","qa","nqa","md","ad","rd",
		argstr="%s",
		sep=":",
		desc="type of value for tract report")
	report_pstyle = traits.Enum(0,1,2,3,4, 
		argstr="%d",
		sep=":",
		requires=["export"],
		desc="profile style for tract report 0:x, 1:y, 2:z, 3:along tracts, "
			"4:tract mean")
	report_bandwidth = traits.Int(
		argstr="%d",
		sep=":",
		requires=["export"],
		desc="bandwidth for tract report")
	report_fa = traits.Bool(desc='export tract report on fa values')
	report_gfa = traits.Bool(desc='export tract report on gfa values')
	report_qa = traits.Bool(desc='export tract report on qa values')
	report_nqa = traits.Bool(desc='export tract report on nqa values')
	report_md = traits.Bool(desc='export tract report on md values')
	report_ad = traits.Bool(desc='export tract report on ad values')
	report_rd = traits.Bool(desc='export tract report on rd values')
		
	connectivity = InputMultiPath(File(exists=True), 
		argstr="--connectivity=%s",
		sep=",",
		desc="atlas id(s), or path to MNI space roi file")
	connectivity_atlas = traits.List(traits.Enum(
			"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
			"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
			"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
			"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
			"talairach","tractography"),
		desc="atlas region id(s)")
	connectivity_type = traits.List(traits.Enum("end","pass"),
		argstr="--connectivity_type=%s",
		sep=",",
		desc="method to count the tracts, default end")
	connectivity_value = traits.List(traits.Str(),
		argstr="--connectivity_value=%s",
		sep=",",
		desc="method to calculate connectivity matrix, default count - n tracks"
			" pass/end in region, ncount - n tracks norm by median length, "
			"mean_length - outputs mean length of tracks, trk - outputs trk "
			"file each matrix entry, other values by reconstruction method, "
			"e.g. 'fa','qa','adc', etc.")
	connectivity_threshold = traits.Float(0.001,
		argstr="--connectivity_threshold=%.3f",
		desc="threshold for calculating binarized graph measures and "
			"connectivity values, def 0.001, i.e. if the max connectivity count"
			" is 1000 tracks in the connectivity matrix, then at least "
			"1000 x 0.001 = 1 track is needed to pass the threshold, "
			"otherwise values will be 0")
	ref = File(exists=True,
		argstr="--ref=%s",
		desc="output track coordinate based on a reference image, "
			"e.g. T1w or T2w")
	cluster = traits.Bool(
		argstr="--cluster=%d,%d,%d,%s",
		requires=["cluster_method_id","cluster_count","cluster_res",
			"cluster_output_fname"],
		desc="whether to run track clustering after fiber tracking")
	cluster_method_id = traits.Enum(0,1,2,
		desc="0:single-linkage, 1:k-means, 2:EM")
	cluster_count = traits.Int(0,
		desc="Total number of clusters assigned in k-means or EM. "
			"In single-linkage, the maximum number of clusters allowed to avoid"
			"over-segmentation.")
	cluster_res = traits.Int(0,
		desc="Mini meter resolution for merging clusters in single-linkage")
	cluster_output_fname = traits.Str(
		desc="Text file name for cluster label output (no spaces)")



class DSIStudioFiberOutputSpec(DSIStudioOutputSpec):
	"""Output specification for fiber tracking, trk, ana"""
	output = File(desc="path/name of fiber track file (if generated)")
	endpt = File(desc="path/name of fiber track end points file "
					  "(if generated)")
	stat_file = File(desc="path/name of fiber track stats file (if generated)")
	tdi_file = File(desc="path/name of fiber track tract density image file "
					    "(if generated)")
	tdi2_file = File(desc="path/name of fiber track tract density image file "
						 "in subvoxel diffusion space (if generated)")
	tdi_color_file = File(desc="path/name of fiber track tract color density "
							  "image file (if generated)")
	tdi_end_file = File(desc="path/name of fiber track tract density image "
							"endpoints file (if generated)")
	tdi2_end_file = File(desc="path/name of fiber track tract density image "
							 "endpoints in subvoxel diffusion space file "
							 "(if generated")
	fa_file = File(desc="path/name of along tract fa values file (if generated)")
	gfa_file = File(desc="path/name of along tract gfa values file (if generated)")
	qa_file = File(desc="path/name of along tract qa values file (if generated)")
	nqa_file = File(desc="path/name of along tract nqa values file (if generated)")
	md_file = File(desc="path/name of along tract md values file (if generated)")
	ad_file = File(desc="path/name of along tract ad values file (if generated)")
	rd_file = File(desc="path/name of along tract rd values file (if generated)")
	report_fa_file = File(desc="path/name of tract report fa values file "
						  "(if generated)")
	report_gfa_file = File(desc="path/name of tract report gfa values file "
						  "(if generated)")
	report_qa_file = File(desc="path/name of tract report qa values file "
						  "(if generated)")
	report_nqa_file = File(desc="path/name of tract report nqa values file "
						  "(if generated)")
	report_md_file = File(desc="path/name of tract report md values file "
						  "(if generated)")
	report_ad_file = File(desc="path/name of tract report ad values file "
						  "(if generated)")
	report_rd_file = File(desc="path/name of tract report rd values file "
						  "(if generated)")



class DSIStudioFiberCommand(DSIStudioCommand):
	"""Not used directly, provides region and post-processing commands for
	DSI Studio trk and ana actions.
	"""
	input_spec = DSIStudioFiberInputSpec
	
	def _regions_update(self):
		"""Update region category ('rois','roas',etc.) with atlas regions"""
		regions = ('rois','roas','ends','seed','ter')
		for name in regions:
			value = getattr(self.inputs, name)
			spec = self.inputs.trait(name)
			argstr = spec.argstr
			sep = spec.sep
			
			#--roi=1 --roi2=2 --roi3=3, same pattern for all regions
			arglist = []
			if not isdefined(value):
				value = []
				
			#change seed and ter values to 1-Lists for loop, others are
			#automatically changed by MultiPath due to InputSpec
			if not isinstance(value, list):
				value = [value]
			lenvalue = len(value)

			#Get values for name_ar
			varnamearlist = []#atlas regions
			varnamearlist.extend((name,'_ar'))
			varnamear = ''.join(varnamearlist)
			nameatlasregions = getattr(self.inputs, varnamear)
			if not isdefined(nameatlasregions):
				nameatlasregions = []
			lennar = len(nameatlasregions)
			
			#Get values for name_atlas
			varnameatlaslist = []
			varnameatlaslist.extend((name,'_atlas'))
			varnameatlas = ''.join(varnameatlaslist)
			nameatlas = getattr(self.inputs, varnameatlas)
			if not isdefined(nameatlas):
				nameatlas = []
			lenna = len(nameatlas)

			#Update
			#File exists check is in InputSpec, so atlas must be in
			#dsistudio_directory/atlas
			if lenna != 0:
				if lennar == lenna:
					for i in range(0,lenna):
						atlas = nameatlas[i]
						update = list_to_str(sep='',
							args=(os.environ['DSIDIR'],'/atlas/',atlas,
								'.nii.gz'))
						#check we havn't already updated
						#True if updated, or more file regions included
						if lenvalue >= lenna:
							#True if not updated
							if value[lenvalue-lenna+i] != update:
								value.append(update)
								setattr(self.inputs, name, value)
								print("Appended atlas: %s to %s" % 
									(atlas,name))
						else:
							value.append(update)
							setattr(self.inputs, name, value)
							print("Appended atlas: %s to %s" % (atlas,name))
				else:
					raise AttributeError("N entries in %s must equal "
						"N entries in %s" %
						(varnamear, varnameatlas))
						
	def _report_update(self):
		"""Update report, report_val from related boolean traits"""
		name = 'report'
		secname = 'report_val'
		secfield = 'values'
		thisbool = getattr(self.inputs, name)
		default_traits = getattr(self.inputs.trait(secname),secfield)
		newvalues = []
		if default_traits is not None:
			for e in default_traits:
				subname = []
				subname.extend((name,'_',e))
				subname = ''.join(subname)
				if isdefined(thisbool) and thisbool:
					subbool = getattr(self.inputs, subname)
					if isdefined(subbool) and subbool:
						newvalues.append(subname)
				else:
					setattr(self.inputs, subname, _Undefined())
			if len(newvalues) > 0:
				setattr(self.inputs, name, True)
				setattr(self.inputs, secname, newvalues)
			else:
				setattr(self.inputs, name, _Undefined())
				setattr(self.inputs, secname, _Undefined())
	
						
	def _export_update(self):
		"""Update export from related traits"""
		name = 'export'
		values = getattr(self.inputs, name)
		if not isdefined(values):
			values = []
		default_traits = getattr(self.inputs, ''.join(('_',name,'_values')))
		
		self._report_update()
		
		newvalues = []
		for e in default_traits:
			subbool = getattr(self.inputs, e)
			if isdefined(subbool):
				if subbool:
					if e not in values:
						newvalues.append(e)
				elif e in values:
					values.remove(e)
		if len(newvalues) + len(values) > 0:
			values.extend(newvalues)
			setattr(self.inputs, name, values)
		else:
			setattr(self.inputs, name, _Undefined())
	
						
	def _check_mandatory_inputs(self):
		"""correct values, then call super"""
		self._update_from_indict()
		self._regions_update()
		self._export_update()
					
		super(DSIStudioFiberCommand, self)._check_mandatory_inputs()
			
			
	def _add_atlas_regions(self, name, value):
		"""helper function for _format_arg,
		will add atlas regions to atlas file paths
		
		Parameters
		----------
		name		: str (input name, e.g. 'seed','rois','roas','ends','ter')
		value		: list(str) (paths or atlas regions, all together for name)
		
		Returns
		-------
		newval : list(str) (atlas with appended :regionname, or path to other)
		"""
				
		lenv = len(value)

		varnamearlist = []
		varnamearlist.extend((name,"_ar"))
		varnamear = ''.join(varnamearlist)
		namear = getattr(self.inputs, varnamear)#matching atlas regions
		
		varnameatlaslist = []
		varnameatlaslist.extend((name,"_atlas"))
		varnameatlas = ''.join(varnameatlaslist)
		nameatlas = getattr(self.inputs, varnameatlas)#matching atlas

		if not isdefined(namear):
			return value #return input if no atlas regions
		else:
			newvalue = []
			newvalue.extend(value) 
			#newvalue = value would lead to checking for file exists, it won't
			lennar = len(namear)
			lenna = len(nameatlas)
			if lennar != lenna:
				raise AttributeError("len( %s ) must equal len( %s )" %
					(varnamear, varnameatlas))
			for i in range(0,lennar):
				atlas = newvalue[lenv-lennar+i]
				ar = namear[i]
				newvallist = []
				newvallist.extend((atlas,":",ar))
				newvalue[lenv-lennar+i] = ''.join(newvallist)
			return newvalue
		
		
	def _add_region_actions(self, name, value):
		"""helper function for _format_arg, 
		will add region action inputs to input value
		
		Parameters
		----------
		name		: str (input name, e.g. 'seed','rois','roas','ends','ter')
		value		: list(str) (paths or atlas regions, all together for name)
		
		Returns
		-------
		newval : list(str) (region name or paths, with appended action options)

		Example
		-------
		trk=Node(interface=DSIStudioTrack())
		trk.inputs.roi=['ROI1.nii','ROI2.nii']
		trk.inputs.roi_actions=[['dilation'],['dilation','smoothing']]
		trk.inputs.cmdline
		'dsi_studio --action=trk --roi=ROI1.nii,dilation --roi2=ROI2.nii,dilation,smoothing'
		"""
		
		varnameactionslist = []
		varnameactionslist.extend((name,"_actions"))
		varnameactions = ''.join(varnameactionslist)
		actions = getattr(self.inputs, varnameactions)#matching action values
		actions_ts = self.inputs.trait(varnameactions)#action values traitspec

		lenval = len(value)
		lenact = len(actions)
		
		if isdefined(actions) and \
		lenact != lenval:
			print('name=%s, value=%s, actions=%s' % (name,value,actions))
			raise AttributeError("N Entries in %s action list does not match "
								 "N Regions (Files + Atlas Regions)" % name)
		
		if not isdefined(actions):#if there are no region actions
			return value#return input
		else:#if there are region actions
			newvalue = []
			for i in range(0,lenact):
				oldval = value[i]
				acts = actions[i]
				if isdefined(actions_ts.sep):
					sep = actions_ts.sep
				else:
					sep = ','
					
				modval = []
				modval.append(oldval)
				
				if acts:#if not an empty list
					modval.append(''.join((
						sep, list_to_str(sep=sep,args=[elt for elt in acts]))))
				newvalue.append(''.join(modval))
			return newvalue
					
		
	def _format_arg(self, name, trait_spec, value):
		"""alternative helper function for _parse_inputs, 
		format rois, roas, ends, seed, ter, export, atlas argstrs
		will not change input, only how it's interpreted
		
		Parameters
		----------
		name : str (input name, from DSIStudioFiberInputSpec)
		trait_spec : trait_spec (input trait_spec from DSIStudioFiberInputSpec)
		value : variable type (input command value)
		
		Returns
		-------
		argstr with value replacing %type in input argstr
		"""

		argstr = trait_spec.argstr
		sep = trait_spec.sep if trait_spec.sep is not None else ' '

		if name == "rois" or \
			name == "roas" or \
			name == "ends" or \
			name == "seed" or \
			name =="ter":
		#--roi=1 --roi2=2 --roi3=3, same pattern for all regions
			arglist = []
			if not isdefined(value):
				value = []
				
			#change seed and ter values to 1-Lists for loop, others are
			#automatically changed by MultiPath due to InputSpec
			if not isinstance(value, list):
				value = [value]
			lenvalue = len(value)

			#Get values for name_ar
			varnamearlist = []#atlas regions
			varnamearlist.extend((name,'_ar'))
			varnamear = ''.join(varnamearlist)
			nameatlasregions = getattr(self.inputs, varnamear)
			if not isdefined(nameatlasregions):
				nameatlasregions = []
			lennar = len(nameatlasregions)
			
			#Get values for name_atlas
			varnameatlaslist = []
			varnameatlaslist.extend((name,'_atlas'))
			varnameatlas = ''.join(varnameatlaslist)
			nameatlas = getattr(self.inputs, varnameatlas)
			#if not isdefined(nameatlas):
				#--roiX=region,actions (--roi%s=%s)
				#nameatlas = []
			#else:
				#--roiX=atlas:region,actions (--roi%s=%s:%s)
				#argstrfixed = argstr.replace('=', '=%s:')
			lenna = len(nameatlas)
			
			#add atlas regions if available, can't add before bcz it
			#wouldn't validate as a file
			#value now includes atlas if it is an input
			valuewar = self._add_atlas_regions(name, value)
			valuewactions = self._add_region_actions(name, valuewar)
					
			for i in range(0,lenvalue):
				if i == 0:
					roin = ''
				elif (name == "rois" or 
					  name == "roas" or 
					  name == "ter") and i > 4:
					print("Cannot have more than 5 %s, first 5 used.\n"
						"%s not included" % 
						(name, ', '.join(value[x] for x in range(i,lenvalue))))
					break
				elif name == "ends" and i > 1:
					print("Cannot have more than 2 ends, first 2 used.\n"
						"%s not included" % 
						(name, ', '.join(value[x] for x in range(i,lenvalue))))
					break
				else:
					roin = i + 1
					
				arglist.append(argstr % (roin, valuewactions[i]))
				
			return sep.join(arglist)
			
		elif name == "export": 
			for e in value:
				if e == "report":
					if isdefined(self.inputs.report_val) and \
					isdefined(self.inputs.report_pstyle) and \
					isdefined(self.inputs.report_bandwidth):
						newe = []
						newe.extend((e,":",
							self.inputs.report_val,":",
							str(self.inputs.report_pstyle),":",
							str(self.inputs.report_bandwidth)))
						i = value.index(e)
						value[i] = "".join(str(newe))
					else:
						raise AttributeError('Export report requested, but not all '
							'required fields: ("report_val", "report_pstyle", '
							'"report_bandwidth") have been set')
			return argstr % sep.join(str(e) for e in value)
			
		elif name == "connectivity":
			if not isdefined(value):
				value = []
				
			conntype = getattr(self.inputs, "connectivity_type")
			connvalue = getattr(self.inputs, "connectivity_value")
			connatlas = getattr(self.inputs, "connectivity_atlas")
			if isdefined(connatlas):
				value.extend(connatlas)
			lenvalue = len(value)
			if lenvalue==len(conntype) and lenvalue==len(connvalue):
				return super(DSIStudioFiberCommand, 
				self._format_arg(name, trait_spec, value))
			else:
				raise IndexError("N inputs for connectivity, connectivity_"
				"type, connectivity_value must be equal")
		
		elif name == "cluster":
			return argstr % (
				getattr(self.inputs, "cluster_method_id"),
				getattr(self.inputs, "cluster_count"),
				getattr(self.inputs, "cluster_res"),
				getattr(self.inputs, "cluster_output_fname"))
		
		else:
			#print('Super: ' + argstr) #debug
			return super(DSIStudioFiberCommand, 
			self)._format_arg(name, trait_spec, value)

	def _parse_inputs(self, skip=None):
		deftoskip = ("report_val",
					"report_pstyle",
					"report_bandwidth")
		if skip is None:
			toskip = deftoskip
		else:
			toskip = []
			toskip.extend(skip)
			toskip.extend(deftoskip)
		return super(DSIStudioFiberCommand, self)._parse_inputs(skip=toskip)
		
	def _list_outputs(self):
		outputs = self._outputs().get()
		texts = ('stat','fa','gfa','qa','nqa','md','ad','rd','report_fa',
				'report_gfa','report_nqa','report_md','report_ad','report_rd')
		imgs = ('tdi','tdi2','tdi_color','tdi_end','tdi2_end')
		for key in outputs.iterkeys():
			inputkey = key.replace('_file','')
			if key == 'output':
				outputs['output'] = self._gen_filename('output')
			elif key == 'endpt' and \
			isdefined(getattr(self.inputs, 'endpt')) and \
			getattr(self.inputs, 'endpt'):
				outputs['endpt'] = self._gen_fname(self._gen_filename('output'),
				suffix='_endpt', change_ext=True, ext=self.inputs.endpt_format)
			elif inputkey in texts and \
			isdefined(getattr(self.inputs, inputkey)) and \
			getattr(self.inputs, inputkey):
				outputs[key] = self.gen_fname(self._gen_filename('output'),
				suffix=''.join(('.', inputkey)), change_ext=True, ext='.txt')
			elif inputkey in imgs and \
			isdefined(getattr(self.inputs, inputkey)) and \
			getattr(self.inputs, inputkey):
				outputs[key] = self.gen_fname(self._gen_filename('output'),
				suffix=''.join(('.', inputkey)), change_ext=True, ext='.nii')

		return outputs



class DSIStudioTrackInputSpec(DSIStudioFiberInputSpec):
	"""Input specification for DSI Studio fiber tracking"""

	output_type = traits.Enum("TRK", "TXT", "NIFTI",
		usedefault=True,
		desc="DSI Studio trk action output type")
	method = traits.Enum(0,1, 
		usedefault=True,
		argstr="--method=%d",
		desc="0:streamline (default), 1:rk4")
	fiber_count = traits.Int(5000, 
		usedefault=True,
		argstr="--fiber_count=%d",
		desc="number of fiber tracks to find, end criterion")
	seed_count = traits.Int(10000000, 
		usedefault=True,
		argstr="--seed_count=%d",
		desc="max number of seeds, end criterion")
	fa_threshold = traits.Float(0.1, 
		usedefault=True,
		argstr="--fa_threshold=%.4f",
		desc="fa theshold or qa threshold depending on rec method")
	threshold_index = traits.Str(
		argstr="--threshold_index=%s",
		requires=["fa_threshold"], 
		desc="assign threshold to another index")
	otsu_threshold = traits.Float(0.6,
		usedefault=True,
		argstr="--otsu_threshold=%.4f",
		desc="Otsu's threshold ratio")
	initial_dir = traits.Enum(0,1,2, 
		argstr="--initial_dir=%d",
		desc="initial propagation direction, 0:primary fiber (default),"
			"1:random, 2:all fiber orientations")
	seed_plan = traits.Enum(0,1, 
		argstr="--seed_plan=%d",
		desc="seeding strategy, 0:subvoxel random(default), 1:voxelwise center")
	interpolation = traits.Enum(0,1,2, 
		argstr="--interpolation=%d",
		desc="interpolation method, 0:trilinear, 1:gaussian radial, "
			"2:nearest neighbor")
	thread_count = traits.Int(2, 
		argstr="--thread_count=%d",
		desc="Assign number of threads to use")
	random_seed = traits.Enum(0,1, 
		argstr="--random_seed=%d",
		desc="whether a timer is used to generate seed points, default is off")
	step_size = traits.Float(1.00, 
		usedefault=True, 
		argstr="--step_size=%.2f", 
		desc="moving distance in each tracking interval, "
			"default is half the spatial resolution, mm")
	turning_angle = traits.Int(60, 
		usedefault=True,
		argstr="--turning_angle=%d", 
		desc="degrees incoming tract dir may differ from outgoing in voxel")
	#listed on website, but didn't seem to be in code, and I don't know
	#what it's supposed to do - leaving out should get default regardless
	#interpo_angle = traits.Int(60, argstr="--interpo_angle=%d", desc="")
	smoothing = traits.Float(0.00, 
		usedefault=True, 
		argstr="--smoothing=%.2f", 
		desc="fiber track momentum")
	min_length = traits.Int(30, 
		usedefault=True, 
		argstr="--min_length=%d", 
		desc="tracks below mm length deleted")
	max_length = traits.Int(300, 
		usedefault=True, 
		argstr="--max_length=%d", 
		desc="tracks above mm length deleted")

		

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
	dsi_studio --action=trk --source=my.fib.gz --output=my.trk.gz --roi=myR1.nii.gz --roi2=myR2.nii.gz --roa=myR3.nii.gz --fa_threshold=0.1 --fiber_count=1000 --seed_count=100000 --method=0 --thread_count=2
	"""

	_action = "trk"
	_output_type = "TRK"
	input_spec = DSIStudioTrackInputSpec
	output_spec = DSIStudioFiberOutputSpec
	
	def _gen_filename(self, name):
		"""Executed if self.inputs.name is undefined, but genfile=True"""
		if name == 'output':
			_, infilename, _ = split_filename(
				os.path.abspath(getattr(self.inputs, 'source')))
			tract_name = getattr(self.inputs, 'tract_name')
			if isdefined(tract_name):
				pfx = ''.join((tract_name,'_'))
			else:
				pfx = ''
			fname = []
			fname.extend((
				pfx,
				infilename,
				DSIInfo.ot_to_ext(self.inputs.output_type)))
			return ''.join(fname)
		else:
			return super(DSIStudioFiberCommand, self)._gen_filename(name)



class DSIStudioAnalysisInputSpec(DSIStudioFiberInputSpec):

	output_type = traits.Enum("NIFTI", "TRK", "TXT",
		usedefault=True,
		desc="DSI Studio ana action output type")
	#if more than 1 roi is given, or tract is specified, DSIstudio will
	#do tract analysis, else region analysis
	tract = File(exists=True, 
		argstr="--tract=%s",
		desc="assign tract file for analysis")
	atlas = traits.List(traits.Enum(
		"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
		"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
		"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
		"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
		"talairach","tractography"),
		argstr="--atlas=%s",
		sep=",",
		desc="atlas name(s) found in dsistudio/build/atlas")



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
	_action = "ana"
	_output_type = "TXT"
	input_spec = DSIStudioAnalysisInputSpec
	output_spec = DSIStudioFiberOutputSpec
	
	def _gen_filename(self, name):
		"""Executed if self.inputs.name is undefined, but genfile=True"""
		if name == 'output':
			tractval = getattr(self.inputs, 'tract')
			tract_name = getattr(self.inputs, 'tract_name')
			sourceval = getattr(self.inputs, 'source')
			
			if isdefined(tract_name):
				pfx = ''.join((tract_name,'_'))
			else:
				pfx = ''
				
			if isdefined(tractval):
				_, infilename, _ = split_filename(os.path.abspath(tractval))
				pfx = ''
			else:
				_, infilename, _ = split_filename(os.path.abspath(sourceval))

			fname = []
			fname.extend((
				pfx,
				infilename,
				DSIInfo.ot_to_ext(self.inputs.output_type)))
			return ''.join(fname)
		else:
			return super(DSIStudioFiberCommand, self)._gen_filename(name)



class DSIStudioSourceInputSpec(DSIStudioInputSpec):
	
	output = File(genfile=True,
		argstr="--output=%s",
		hash_files=False,
		desc="assign the output src file path and name",
		position=3)
	output_type = traits.Enum("SRC",
		usedefault=True,
		desc="DSI Studio src action output type")
	b_table = File(exists=True,
		argstr="--b_table=%s",
		xor=["bval","bvec"],
		desc="assign the replacement b-table")
	bval = File(exists=True,
		argstr="--bval=%s",
		xor=["b_table"],
		desc="assign the b value text file")
	bvec = File(exists=True,
		argstr="--bvec=%s",
		xor=["b_table"],
		desc="assign the b vector text file")
	recursive = traits.Enum(0,1,
		argstr="--recursive=%d",
		desc="whether to search files in subdirectories")



class DSIStudioSourceOutputSpec(DSIStudioOutputSpec):
	
	output = File(exists=False,
		desc="DSI Studio src file")



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
	_action = "src"
	_output_type = "SRC"
	input_spec = DSIStudioSourceInputSpec
	output_spec = DSIStudioSourceOutputSpec

	def _gen_filename(self, name):
		if name == "output":
			out = self.inputs.output
			if not isdefined(out) and isdefined(self.inputs.source):
				out = self._gen_fname(self.inputs.source, change_ext=True)
			return os.path.abspath(out)
		else:
			return super(DSIStudioSource, self)._gen_filename(name)
			
	def _list_outputs(self):
		outputs = self._output_spec().get()
		outputs['output'] = self._gen_filename('output')
		return outputs
		
	def _check_mandatory_inputs(self):
		"""Update other inputs from inputs.indict then call super"""
		self._update_from_indict()
		super(DSIStudioSource, self)._check_mandatory_inputs()



class DSIStudioReconstructInputSpec(DSIStudioInputSpec):
	
	thread_count = traits.Int(2, 
		argstr="--thread_count=%d",
		desc="Number of threads to use for reconstruction")
	mask = File(exists=True, 
		argstr="--mask=%s",
		desc="assign a nifti format mask")
	output_type = traits.Enum("FIB", 
		usedefault=True,
		desc="DSI Studio rec action output type")
	method_dsi = traits.Bool(
		xor=["method_dti","method_frqbi","method_shqbi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=list(DSIInfo.rec_mid_to_req('dsi')),
		desc="assign DSI method for reconstruction")
	method_dti = traits.Bool(
		xor=["method_dsi","method_frqbi","method_shqbi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=list(DSIInfo.rec_mid_to_req('dti')),
		desc="assign DTI method for reconstruction")
	method_frqbi = traits.Bool(
		xor=["method_dti","method_dsi","method_shqbi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=list(DSIInfo.rec_mid_to_req('frqbi')),
		desc="assign Funk-Radon QBI method for reconstruction")
	method_shqbi = traits.Bool(
		xor=["method_dti","method_frqbi","method_dsi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=list(DSIInfo.rec_mid_to_req('shqbi')),
		desc="assign Spherical Harmonic QBI method for reconstruction")
	method_gqi = traits.Bool(
		xor=["method_dti","method_frqbi","method_shqbi","method_dsi",
			"method_hardi","method_qsdr"],
		requires=list(DSIInfo.rec_mid_to_req('gqi')),
		desc="assign GQI method for reconstruction")
	method_hardi = traits.Bool(
		xor=["method_dti","method_frqbi","method_shqbi","method_gqi",
			"method_dsi","method_qsdr"],
		requires=list(DSIInfo.rec_mid_to_req('hardi')),
		desc="Convert to HARDI")
	method_qsdr = traits.Bool(
		xor=["method_dti","method_frqbi","method_shqbi","method_gqi",
			"method_hardi","method_dsi"],
		requires=list(DSIInfo.rec_mid_to_req('qsdr')),
		desc="assign QSDR method for reconstruction")
							
	method = traits.Enum('dti','dsi','frqbi','shqbi','gqi','hardi','qsdr',
		mandatory=True, 
		argstr="--method=%d",
		desc="Reconstruction method, DSI:0, DTI:1, Funk-Randon QBI:2, "
			"Spherical Harmonic QBI:3, GQI:4, Convert to HARDI:6, QSDR:7")

	#params includes some floats, some ints depending on method, but dsi studio
	#actually reads them all as floats, so should be fine here
	param = traits.List(traits.Float(),
		argstr="--param%s=%s",
		desc="Reconstruction parameters, different meaning and types for "
			"different methods")
	#param0 = traits.Float(desc="param 0 for method")
	#param1 = traits.Float(desc="param 1 for method")
	#param2 = traits.Float(desc="param 2 for method")
	#param3 = traits.Float(desc="param 3 for method")
	#param4 = traits.Float(desc="param 4 for method")
	
	affine = File(exists=True, 
		argstr="--affine=%s",
		desc="text file containing a transformation matrix. e.g. the following "
		"shifts in x and y by 10 voxels: \n1 0 0 -10 \n 0 1 0 -10 \n 0 0 1 0")
	flip = traits.Int(
		argstr="--flip=%d", 
		desc="flip image volume and b-table. 0:flip x, 1:flip y, 2:flip z, "
			"3:flip xy, 4:flip yz, 5: flip xz. \n"
			"e.g. 301 performs flip xy, flip x, flip y")
	motion_corr = traits.Enum(0,1, 
		usedefault=True,
		argstr="--motion_correction=%d",
		desc="whether to apply motion and eddy correction, only DTI dataset")
	check_btable = traits.Enum(1,0, 
		usedefault=True,
		argstr="--check_btable=%d",
		desc="whether to do b-table flipping, default yes")
	hanning_filter_width = traits.Int(16,
		usedefault=True,
		desc="DSI - Hanning filter width")
	output_dif = traits.Enum(1,0, 
		usedefault=True,
		argstr="--output_dif=%d",
		desc="DTI - output diffusivity, default 1")
	output_tensor = traits.Enum(0,1, 
		usedefault=True,
		argstr="--output_tensor=%d",
		desc="DTI - output whole tensor, default 0")
	smooth_kernel_width = traits.Int(15,
		usedefault=True,
		desc="FRQBI - width of gaussian smoothing kernel")
	interp_kernel_width = traits.Int(5,
		usedefault=True,
		desc="FRQBI - width of interpolation kernel")
	odf_order = traits.Enum(8,4,5,6,10,12,16,20, 
		usedefault=True,
		argstr="--odf_order=%d",
		desc="FRQBI,SHQBI,GQI,QSDR - tesselation number of the odf, default 8")
	record_odf = traits.Enum(0,1, 
		usedefault=True,
		argstr="--record_odf=%d",
		desc="FRQBI,SHQBI,GQI,QSDR - whether to output ODF for connectometry "
			"analysis")
	regularization = traits.Float(0.006,
		desc="FRQBI,SHQBI,GQI,QSDR - regularization parameter")
	harmonic_order = traits.Int(8,
		usedefault=True,
		desc="SHQBI - order of spherical harmonics")
	mddr = traits.Float(1.25,
		usedefault=True,
		desc="GQI - ratio of the mean diffusion distance")
	r2_weighted = traits.Enum(0,1, 
		usedefault=True,
		argstr="--r2_weighted=%d",
		desc="GQI - whether to apply r2 weighted reconstruction")
	output_rdi = traits.Enum(1,0, 
		usedefault=True,
		argstr="--output_rdi=%d",
		desc="GQI,QSDR - output restricted diffusion imaging, default 1")
	csf_cal = traits.Enum(1,0, 
		usedefault=True,
		argstr="--csf_calibration=%d",
		desc="GQI,QSDR - enable CSF calibration, default 1")
	b_value = traits.Int(3000,
		usedefault=True,
		desc="HARDI - b-value")
	output_resolution = traits.Float(2,
		usedefault=True,
		desc="QSDR - output resolution in mm")
	#--other_image=t1w,/directory/my_t1w.nii.gz;t2w,/directory/my_t1w.nii.gz
	other_image = traits.Bool(
		argstr="--other_image=%s,%s",
		sep=";",
		requires=["other_image_type","other_image_file"],
		desc="QSDR - whether to wrap other image volumes")
	other_image_type = traits.List(traits.Enum("t1w","t2w"),
		requires=["other_image","other_image_file"],
		desc="QSDR - t1w or t2w (maybe others, but unsure,unimplemented)")
	other_image_file = InputMultiPath(File(exists=True), 
		requires=["other_image","other_image_type"],
		desc="QSDR - filepath for image to be wrapped")
	output_mapping = traits.Enum(0,1, 
		usedefault=True,
		argstr="--output_mapping=%d",
		desc="QSDR - output mapping for each voxel, default 0")
	output_jac = traits.Enum(0,1, 
		usedefault=True,
		argstr="--output_jac=%d",
		desc="QSDR - output jacobian determinant, default 0")
	interpolation = traits.Enum(0,1,2, 
		usedefault=True,
		argstr="--interpolation=%d",#says interpo_method in docs, but not code
		desc="QSDR - interpolation method, 0:trilinear (default), "
			"1:gaussian radial basis, 2:tricubic")
	num_fiber = traits.Int(5, 
		usedefault=True,
		argstr="--num_fiber=%d",
		desc="FRQBI,SHQBI,GQI,QSDR - max count of resolving fibers per voxel, "
			"default 5")
	deconvolution = traits.Enum(0,1, 
		usedefault=True,
		argstr="--deconvolution=%d",
		desc="whether to apply deconvolution, requires regularization")
	decomposition = traits.Enum(0,1, 
		usedefault=True,
		argstr="--decomposition=%d",
		desc="whether to apply decomposition, requires decomp_frac, m_value")
	decomp_frac = traits.Float(0.05,
		usedefault=True,
		requires=["decomposition"],
		desc="decomposition fraction")
	m_value = traits.Int(10,
		usedefault=True,
		requires=["decomposition"],
		desc="decomposition m value")
	regist_method = traits.Enum(0,1,2,3,4, 
		usedefault=True,
		argstr="--reg_method=%d",
		desc="QSDR - registration method 0:SPM 7-9-7, 1:SPM 14-18-14, "
			"2:SPM 21-27-21, 3:CDM, 4:T1W-CDM")
	t1w = File(exists=True, 
		argstr="--t1w=%s", 
		requires=["regist_method"],
		desc="QSDR - assign a t1w file for registration method 4")
	template = File(exists=True,
		argstr="--template=%s",
		desc="QSDR - assign a template file for spatial normalization")



class DSIStudioReconstructOutputSpec(DSIStudioOutputSpec):
	"""DSI Studio reconstruct output specification"""
	fiber_file = File(exists=True, desc="Fiber tracking file")
	#filename depends on reconstruction method, and automatic detections by
	#DSIStudio, unsure how to tell nipype workflow about all of it
#Decoding the file extension
#The FIB file generated during the reconstruction will include several extension. 
#Here is a list of the explanation
#odf8: An 8-fold ODF tessellation was used
#f5: For each voxel, a maximum of 5 fiber directions were resolved
#rec: ODF information was output in the FIB file
#csfc: quantitative diffusion MRI was conducted using CSF location as the free 
#water calibration
#hs: A half sphere scheme was used to acquired DSI
#reg0i2: the spatial normalization was conducted using 
#(reg0: 7-9-7 reg1: 14-18-14 reg2: 21-27-21) and the images were interpolated 
#using (i0: trilinear interpolation, I1: Guassian radial basis i2: cubic spine)
#bal: The diffusion scheme was resampled to ensure balance in the 3D space
#fx, fy, fz: The b-table was automatically flipped by DSI Studio in x-, y-, or 
#z- direction. 012 means the order of the x-y-z coordinates is the same, 
#whereas 102 indicates x-y flip, 210 x-z flip, and 021 y-z- flip. 
#rdi: The restricted diffusioin imaging metrics were calculated 
#de: deconvolution was used to sharpen the ODF
#dec: decomposition was used to sharpen the ODF
#dti: The images were reconstructed using diffusion tensor imaging
#gqi: The images were reconstructed using generalized q-sampling imaging
#qsdr: The images were reconstructed using q-space diffeomorphic reconstruction
#R72: The goodness-of-fit between the subject's data and the template has a R-squared value of 0.72

###TODO Capture from stdout

class DSIStudioReconstruct(DSIStudioCommand):
	"""DSI Studio reconstruct action support
	TESTING
	"""
	_action = "rec"
	_output_type = "FIB"
	input_spec = DSIStudioReconstructInputSpec
	output_spec = DSIStudioReconstructOutputSpec
	#terminal_output = 'stream'
	
	def __init__(self, **inputs):
		super(DSIStudioReconstruct, self).__init__(**inputs)
		
		self.inputs.on_trait_change(self._method_update, 'method')
		self.inputs.on_trait_change(self._param_update, 'param')
		
	def _deconv_update(self):
		dcnv = 'deconvolution'
		dcnvval = getattr(self.inputs, dcnv)
		dcnvspec = self.inputs.trait(dcnv)
		paramspec = self.inputs.trait('param')
		paramval = getattr(self.inputs, 'param')
		subparams = ('regularization',)
		if not isdefined(dcnvval) or dcnvval == 0:
			setattr(dcnvspec, 'requires', None)
			for e in subparams:
				if paramspec.requires is not None and e in paramspec.requires:
					paramspec.requires.remove(e)
		elif dcnvval == 1:
			setattr(dcnvspec, 'requires', list(subparams))
			if paramspec.requires is None:
				paramspec.requires = []
			paramspec.requires.extend(subparams)
		
	def _decomp_update(self):
		dcmp = 'decomposition'
		dcmpval = getattr(self.inputs, dcmp)
		dcmpspec = self.inputs.trait(dcmp)
		paramspec = self.inputs.trait('param')
		paramval = getattr(self.inputs, 'param')
		subparams = ('decomp_frac', 'm_value')
		if not isdefined(dcmpval) or dcmpval == 0:
			setattr(dcmpspec, 'requires', None)
			for e in subparams:
				if paramspec.requires is not None and e in paramspec.requires:
					paramspec.requires.remove(e)
		elif dcmpval == 1:
			setattr(dcmpspec, 'requires', list(subparams))
			if paramspec.requires is None:
				paramspec.requires = []
			paramspec.requires.extend(subparams)
				
	def _param_update(self):
		name = 'param'
		value = getattr(self.inputs, name)
		spec = self.inputs.trait(name)		
		
		self._deconv_update()
		self._decomp_update()	
		
		mval = getattr(self.inputs, 'method')
		if isdefined(mval):
			#update param values, requires, and mandatory flag based on method
			paramsources = DSIInfo.rec_mid_to_pids(mval)
			nparams = len(paramsources)
			requires = getattr(spec, 'requires')
			if requires is None:
				requires = []
			if nparams > 0:
				setattr(spec, 'mandatory', True)
				requires.extend(paramsources)
				setattr(spec, 'requires', requires)
				paramlist = []
				for e in requires:
					paramval =  getattr(self.inputs, e)
					if isdefined(paramval):
						paramlist.append(paramval)
					else:
						raise TypeError('Input: %s is <undefined>, required '
							'parameter for Method: %s' %
							(e, mval))
				setattr(self.inputs, name, paramlist)
			else:
				setattr(spec, 'mandatory', None)
				setattr(spec, 'requires', None)
				#Defaults are actually to not be in spec.__dict__, but None
				#should/seems to work the same
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
		
		##if method defined, set method_value to True, other methods to False
		#if isdefined(value):
			#idname = []
			#idname.extend(('method_',value))
			#varidname = ''.join(idname)
			#fix = self.inputs.trait(varidname)
			#for x in fix.xor:
				#setattr(self.inputs, x, _Undefined())
			#setattr(self.inputs, varidname, True)
		#else:
			##sfx is 'dsi', 'dti' etc.
			#for sfx in DSIInfo.rec_method_id_n.iterkeys():
				#idname =[]
				#idname.extend(('method_',sfx))
				#varidname = ''.join(idname)
				#sfxvalue = getattr(self.inputs, varidname)
				#if isdefined(sfxvalue) and sfxvalue == True:
					#newval = sfx
					#setattr(self.inputs, 'method', newval)
		
			
	def _check_mandatory_inputs(self):
		"""using this to insert/update necessary values, then call super
		_check_mandatory_inputs called before any cmd is run
		"""
		self._update_from_indict()
		self._method_update()

		#run original _check_mandatory_inputs
		super(DSIStudioReconstruct, self)._check_mandatory_inputs()

	def _format_arg(self, name, trait_spec, value):
		"""alternative helper function for _parse_inputs, 
		only include specific argstrs for the reconstruction method,
		format method specific argstrs, params, other_image_...,
		
		Parameters
		----------
		name : str (input spec variable)
		trait_spec : trait_spec (self.inputs.name.traits())
		value: various (self.inputs.name)
		"""

		argstr = trait_spec.argstr
		#print argstr #debug
		sep = trait_spec.sep if trait_spec.sep is not None else " "
		arglist = []
		
		if name == "method":
			#method id to n
			return argstr % DSIInfo.rec_mid_to_mn(value)
			
		if name == "param":
			#method should be defined, parsed in alphabetical order
			recmid = getattr(self.inputs, 'method')
			expparamtypes = DSIInfo.rec_mid_to_ptype(recmid)
			if recmid == "DTI":
				pass #no params
			
			if len(value) == expnparams:
				for e in value:
					e_idx = value.index(e)
					if isinstance(e, DSIInfo.rec_mid_to_ptype(
						recmid)[e_idx]):
						#numbered from 0
						arglist.append(argstr % (e_idx,e))
					else:
						raise AttributeError("Param type: %s != Expected "
							"Param type: %s for Param: %s, in Method: %s" %
							(type(e),expparamtypes[e_idx],e,
							recmid))
				return sep.join(arglist)
			else:
				raise AttributeError("N input params: '%d' != "
									"Expected N params: '%d' for Method: %s" %
									(len(value),expnparams,recmid))
									
		#qsdr t1w,t2w image wrapping, check number of inputs match and put 
		#values in other_image argstr
		elif name == "other_image" and value:
			oit = self.inputs.other_image_type
			oif = self.inputs.other_image_file
			_, argstrend = argstr.split('=')
			if len(oit) == len(oif):
				for t in oit:
					if oit.index(t) == 0:
						arglist.append(argstr % (t, oif[oit.index(t)]))
					#in case there are more than 2 options in future
					elif oit.index(t) < len(oit):
						arglist.append(argstrend % (t, oif[oit.index(t)]))
				return sep.join(arglist)
			else:
				raise AttributeError("N other image types != N other image "
									"files")
		else:
			return super(DSIStudioReconstruct, self)._format_arg(
			name, trait_spec, value)

	def _parse_inputs(self, skip=None):
		#super._parse_inputs any var with an argstr will be parsed if not in skip
		recmid = getattr(self.inputs, 'method')
		incp=set(DSIInfo.rec_method_id_inputs[recmid])
		allp = set().union(*DSIInfo.rec_method_id_inputs.itervalues())
		excp = allp.difference(incp)
		deftoskip =[]
		for elt in excp:
			deftoskip.append(elt)
		
		if skip is None:
			toskip = deftoskip
		else:
			toskip = []
			deftoskip.extend(skip)
			toskip.extend(deftoskip)
		return super(DSIStudioReconstruct, self)._parse_inputs(skip=toskip)
		
	def _list_outputs(self):
		outputs = self._outputs().get()
		#This is not quite correct, as described in outputspec
		ext = []
		ext.append(self.inputs.method)
		ext.append(DSIInfo.ot_to_ext(self.inputs.output_type))
		ext = ''.join(ext)
		outputs['fiber_file'] = self._gen_fname(
			self.inputs.source, change_ext=True, ext=ext)
		return outputs
		
	def aggregate_outputs(self, runtime=None, needed_outputs=None):
		"""DSIStudio reconstruct will write the output to the input directory
		with a variable filename, but puts this information in stdout. Copy and 
		fix.
		"""
		return super(DSIStudioReconstruct, self).aggregate_outputs(
			runtime=runtime, needed_outputs=needed_outputs)
	
	#copied from nipype.interfaces.base.core.CommandLine for debugging
	def _run_interface(self, runtime, correct_return_codes=(0,)):
		"""Execute command via subprocess

		Parameters
		----------
		runtime : passed by the run function

		Returns
		-------
		runtime : updated runtime information
			adds stdout, stderr, merged, cmdline, dependencies, command_path

		"""
		import shlex
		from nipype.utils.filemanip import which, get_dependencies

		out_environ = self._get_environ()
		# Initialize runtime Bunch
		runtime.stdout = None
		runtime.stderr = None
		runtime.cmdline = self.cmdline
		runtime.environ.update(out_environ)

		# which $cmd
		executable_name = shlex.split(self._cmd_prefix + self.cmd)[0]
		cmd_path = which(executable_name, env=runtime.environ)

		if cmd_path is None:
			raise IOError(
				'No command "%s" found on host %s. Please check that the '
				'corresponding package is installed.' % (executable_name,
														 runtime.hostname))

		runtime.command_path = cmd_path
		runtime.dependencies = (get_dependencies(executable_name,
												 runtime.environ)
								if self._ldd else '<skipped>')
		runtime = run_command(runtime, output=self.terminal_output)
		
		if runtime.returncode is None or \
				runtime.returncode not in correct_return_codes:
			self.raise_exception(runtime)

		return runtime



class DSIStudioAtlasInputSpec(DSIStudioInputSpec):
	order = traits.Enum(0,1,2,3,
						argstr="--order=%d",
						desc="normalization order, higher gives better acc. "
							"but requires more time, default 0")
	thread_count = traits.Int(4,
							argstr="--thread_count=%d",
							desc="number of threads to use in image "
								"normalization, default 4")
	atlas = traits.List(
		traits.Enum("aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
					"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
					"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
					"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
					"talairach","tractography"),
		argstr="--atlas=%s", 
		sep=",")
	output = traits.Enum("single", "multiple",
						argstr="--output=%s",
						desc="whether to create one or multiple nifti files")
	output_type = traits.Enum("NIFTI",
							usedefault=True,
							desc="DSI Studio atlas action output type")



class DSIStudioAtlasOutputSpec(DSIStudioOutputSpec):
	output = OutputMultiPath(
				File(desc="path/name of transformed atlas nifti file(s) "
							"(if generated)"))



class DSIStudioAtlas(DSIStudioCommand):
	"""DSI Studio atlas action support
	TESTING
	"""
	_action = "atl"
	_output_type = "NIFTI"
	input_spec = DSIStudioAtlasInputSpec

	def _check_mandatory_inputs(self):
		"""Update other inputs from inputs.indict then call super"""
		self._update_from_indict()
		super(DSIStudioAtlas, self)._check_mandatory_inputs()

class DSIStudioExportInputSpec(DSIStudioInputSpec):
	export = traits.List(
				traits.Str(),
				argstr="--export=%s",
				name_source=["source"],
				name_template="%s",#overload extension, don't add _generated
				desc="name of export target, includes fa0,fa1,gfa,dir0,dir1,"
					"dirs,image0,4dnii, maybe others")
	output_type = traits.Enum("NIFTI",
							usedefault=True,
							desc="DSI Studio Export output type")



class DSIStudioExportOutputSpec(DSIStudioOutputSpec):
	export = OutputMultiPath(
				File(exists=True),
				desc="matrix information output as nifti files")



class DSIStudioExport(DSIStudioCommand):
	"""DSI Studio export action support for exporting matrix information
	TESTING
	"""
	_action = "exp"
	_output_type = "NIFTI"
	input_spec = DSIStudioExportInputSpec
	output_spec = DSIStudioExportOutputSpec

	def _overload_extension(self, value, name):
		ns = self.inputs.trait(name).name_source
		source = getattr(self.inputs, ns[0])
		retval = []
		rvunjoined = []
		for e in value:
			rvunjoined.extend((source, 
				e,#DSI Studio adds export target to ext
				DSIInfo.ot_to_ext(self.inputs.output_type)))
		for e in rvunjoined:
			retval.append("".join(e))
		return retval
		
	def _check_mandatory_inputs(self):
		"""Update other inputs from inputs.indict then call super"""
		self._update_from_indict()
		super(DSIStudioExport, self)._check_mandatory_inputs()

