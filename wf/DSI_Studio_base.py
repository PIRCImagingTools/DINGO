from nipype.interfaces.base import (traits, File, Directory, InputMultiPath, 
									OutputMultiPath,isdefined, 
									CommandLine, CommandLineInputSpec, 
									TraitedSpec)
import os
from nipype.utils.filemanip import fname_presuffix, split_filename
from traits.trait_base import _Undefined



class Info(object):
	#file extensions for output types
	ftypes = {
		'SRC': '.src.gz',
		'FIB': '.fib.gz',
		'NIFTI': '.nii.gz',
		'TRK': '.trk.gz',
		'TXT': '.txt'}

	#primary output types for action types
	act_out = {
		'trk': 'TRK',
		'rec': 'FIB',
		'src': 'SRC',
		'ana': 'TXT',
		'atl': 'NIFTI'}

	#reconstruction method id for method number
	rec_method_n_id = {
		0: 'DSI',
		1: 'DTI',
		2: 'QBI',
		3: 'QBI',
		4: 'GQI',
		6: 'HARDI',
		7: 'QSDR'}
	
	#reconstruction method number of params for method id	   
	rec_nparams = {
		'DSI': 1,
		'DTI': 0,
		'QBI': 2,
		'GQI': 1,
		'QSDR': 2,
		'HARDI': 3}
	
	#reconstruction method param types for method id
	rec_param_types = {
		'DSI': [int],
		'DTI': [None],
		'QBI': [float,int],
		'GQI': [float],
		'QSDR': [float,int],
		'HARDI': [float,int,float]}
				
	#reconstruction method param ids for method id
	#NOT NECESSARILY LINKED TO rec_nparams, rec_param_types
	rec_method_id_params = {
		'DSI': ['hanning_filter_width'],
		'DTI': ['output_dif','output_tensor'],
		'QBI': [float,int],
		'GQI': [float],
		'QSDR': [float,int],
		'HARDI': [float,int,float]}

	@classmethod
	def output_type_to_ext(cls, output_type):
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
			msg = 'Invalid DSIStudioOUTPUTTYPE: ', output_type
			raise KeyError(msg)

	@classmethod
	def action_to_output_type(cls, action_type):
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
			msg = 'Invalid DSIStudioACTIONTYPE: ', action_type
			raise KeyError(msg)
			
	@classmethod
	def rec_method_n_to_id(cls, method_n):
		"""Get DSI Studio tracking method id per method number
		
		Parameter
		---------
		method_n : {0,1,2,3,4,6,7}
			Int specifying reconstruction method number
		
		Returns
		-------
		method_id : str
		"""
		try:
			return cls.rec_method_n_id[method_n]
		except KeyError:
			msg = 'Invalid DSIStudio method number: ', method_n
			raise KeyError(msg)
			
	@classmethod
	def rec_method_to_nparams(cls, method_id):
		"""Get number of params per tracking method
		
		Parameter
		---------
		method : {'DSI','DTI','QBI','GQI','HARDI','QSDR'}
			Str specifying reconstruction method
		
		Returns
		-------
		nparams : int
		"""
		try:
			return cls.rec_nparams[method_id]
		except KeyError:
			msg = 'Invalid DSIStudio Tracking method: ', method_id
			raise KeyError(msg)
			
	@classmethod
	def rec_method_to_param_types(cls, method_id):
		"""Get param types per tracking method
		
		Parameter
		---------
		method : {'DSI','DTI','QBI','GQI','HARDI','QSDR'}
			Str specifying reconstruction method
		
		Returns
		-------
		type
		"""
		try:
			return cls.rec_param_types[method_id]
		except KeyError:
			msg = 'Invalid DSIStudio Tracking method: ', method_id
			raise KeyError(msg)



class DSIStudioInputSpec(CommandLineInputSpec):
	"""Base input specification for DSI Studio commands."""

	action = traits.Enum("trk","ana",
						 "src","rec","atl","exp","cnt","vis","ren",
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
	debuglog = File(argstr="> %s",
					desc="Log file path/name")



class DSIStudioOutputSpec(TraitedSpec):
	debuglog = File(desc="path/name of log file (if generated)")
	


class DSIStudioCommand(CommandLine):
	"""Base support for DSI Studio commands.
	"""
	_cmd = "dsi_studio"
	_output_type = None
	_action = None

	input_spec = DSIStudioInputSpec

	def __init__(self, **inputs):
		super(DSIStudioCommand, self).__init__(**inputs)
		self.inputs.on_trait_change(self._output_update, 'output_type')
		self.inputs.on_trait_change(self._action_update, 'action')

		if self._action is None:#should be specified in subclass
			raise Exception("Missing action command")

		if self._output_type is None:
			self._output_type = Info.action_to_output_type(self._action)

		if not isdefined(self.inputs.output_type):
			self.inputs.output_type = self._output_type
		else:
			self._output_update()

		if not isdefined(self.inputs.action):
			self.inputs.action = self._action
		else:
			self._action_update()

	@property
	def action(self):
		return self._action

	def _output_update(self):
		self._output_type = self.inputs.output_type

	def _action_update(self):
		self._action = self.inputs.action

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
			ext = Info.output_type_to_ext(self.inputs.output_type)
		if change_ext:
			if suffix:
				suffix = "".join((suffix, ext))
			else:
				suffix = ext
		if suffix is None:
			suffix = ""
		fname = fname_presuffix(basename, suffix=suffix, use_ext=True,
								newpath=cwd)
		return fname

				  


class DSIStudioFiberInputSpec(DSIStudioInputSpec):
	"""Provides region and post-processing input
	specification used with DSI Studio trk and ana actions.
	"""
	#ROI Parameters
	seed = traits.Either(
		File(exists=True),
		traits.Str(requires=["atlas"]),
		argstr="--seed=%s",
		desc="specify seeding file, txt, analyze, or nifti, unspecified default"
			" is whole brain")
	seed_action = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		requires = ["seed"],
		argstr="%s",
		sep=",",
		desc="action codes to modify seed region")
	#DSI Studio has built in accepted values that are not file paths,
	#but AtlasName:RegionName
	roi = traits.Either(
		InputMultiPath(File(exists=True)), 
		traits.List(traits.Str, requires=["atlas"]),#region name(s) in atlas
		argstr="--roi%s=%s",
		desc="roi through which tracts must pass, txt, analyze, nifti, "
				"or region in atlas")
	roi_action = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		requires = ["roi"],
		argstr="%s",
		sep=",",
		desc="action codes to modify rois, list for each roi")
	roa = traits.Either(
		InputMultiPath(File(exists=True)), 
		traits.List(traits.Str, requires=["atlas"]), 
		argstr="--roa%s=%s",
		desc="roa files which tracts must avoid, txt, analyze, nifti, "
			"or region in atlas")
	roa_action = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		requires = ["roa"],
		argstr="%s",
		sep=",",
		desc="action codes to modify roas, list for each roa")
	end = traits.Either(
		InputMultiPath(File(exists=True)), 
		traits.List(traits.Str, requires=["atlas"]),
		argstr="--end%s=%s",
		desc="filter out tracks that do not end in this region, txt, analyze, "
			"nifti or region in atlas")
	end_action = traits.List(traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		requires = ["end"],
		argstr="%s",
		sep=",",
		desc="action codes to modify ends regions, list for each end")
	ter = traits.Either(
		File(exists=True), 
		traits.List(traits.Str, requires=["atlas"]),
		argstr="--ter=%s",
		desc="terminates any track that enters this region, txt, analyze, "
			"nifti, or region in atlas")
	ter_action = traits.List(
		traits.List(traits.Enum(
				"smoothing","erosion","dilation","defragment","negate",
				"flipx","flipy","flipz",
				"shiftx","shiftnx","shifty","shiftny","shiftz","shiftnz")),
		requires = ["ter"],
		argstr="%s",
		sep=",",
		desc="action codes to modify terminative region")
	t1t2 = File(exists=True,
				argstr="--t1t2=%s",
				desc="specify t1w or t2w images as roi reference image")
	atlas = traits.List(traits.Enum(
			"aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
			"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
			"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
			"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
			"talairach","tractography"),
		argstr="--atlas=%s", 
		sep=",")
	
	#Post-Process Parameters
	delete_repeat = traits.Enum(0,1, 
		argstr="--delete_repeat=%d",
		desc="0 or 1, 1 removes repeat tracks with distance < 1 mm")
	track = File(genfile=True,
		argstr="--output=%s",
		hash_files=False,
		desc="output tract file name, format may be txt, trk, or nii",
		position=3)
	endpt = File(#maybe genfile
		argstr="--end_point=%s",
		hash_files=False,
		desc="endpoint file name, format may be txt or mat")
	export = traits.List(traits.Enum(
			"stat","tdi","tdi2","tdi_color","tdi_end",
			"tdi2_end","fa","gfa","qa","nqa","md","ad","rd","report"),
		argstr="--export=%s", 
		sep=',',
		desc="export information related to fiber tracts")
	report_val = traits.Enum("fa","gfa","qa","nqa","md","ad","rd",
		argstr="%s",
		sep=":",
		desc="type of values for tract report")
	report_pstyle = traits.Enum(0,1,2,3,4, 
		argstr="%d",
		sep=":",
		requires=["export"],
		desc="profile style for tract report 0:x, 1:y, 2:z, 3:along tracts, "
			"4:tract mean")
	report_bandwidth = traits.Float(1.0, 
		argstr="%.1f",
		sep=":",
		requires=["export"],
		desc="bandwidth for tract report")
	connectivity = traits.Either(
		InputMultiPath(File(exists=True)), 
		traits.List(atlas, requires=["atlas"]),
		argstr="--connectivity=%s",
		sep=",",
		desc="atlas id(s), or path to MNI space roi file")
	connectivity_type = traits.List(traits.Enum("end","pass"),
		argstr="--connectivity_type=%s",
		sep=",",
		requires=["connectivity"],
		desc="method to count the tracts, default end")
	connectivity_value = traits.List(traits.Str(),
		argstr="--connectivity_value=%s",
		sep=",",
		requires=["connectivity"],
		desc="method to calculate connectivity matrix, default count - n tracks"
			" pass/end in region, ncount - n tracks norm by median length, "
			"mean_length - outputs mean length of tracks, trk - outputs trk "
			"file each matrix entry, other values by reconstruction method, "
			"e.g. 'fa','qa','adc', etc.")
	connectivity_threshold = traits.Float(0.001,
		argstr="--connectivity_threshold=%.3f",
		requires=["connectivity"],
		desc="threshold for calculating binarized graph measures and "
			"connectivity values, def 0.001, i.e. if the max connectivity count"
			" is 1000 tracks in the connectivity matrix, then at least "
			"1000 x 0.001 = 1 track is needed to pass the threshold, "
			"otherwise values will be 0")
	ref = File(exists=True,
		argstr="--ref=%s",
		desc="output track coordinate based on a reference image, "
			"e.g. T1w or T2w")



class DSIStudioFiberOutputSpec(DSIStudioOutputSpec):
	"""Output specification for fiber tracking, trk, ana"""
	track = File(desc="path/name of fiber track file (if generated)")
	endpt = File(desc="path/name of fiber track end points file "
					  "(if generated)")
	stat = File(desc="path/name of fiber track stats file (if generated)")
	tdi = File(desc="path/name of fiber track tract density image file "
					    "(if generated)")
	tdi2 = File(desc="path/name of fiber track tract density image file "
						 "in subvoxel diffusion space (if generated)")
	tdi_color = File(desc="path/name of fiber track tract color density "
							  "image file (if generated)")
	tdi_end = File(desc="path/name of fiber track tract density image "
							"endpoints file (if generated)")
	tdi2_end = File(desc="path/name of fiber track tract density image "
							 "endpoints in subvoxel diffusion space file "
							 "(if generated")
	fa = File(desc="path/name of along tract fa values file (if generated)")
	gfa = File(desc="path/name of along tract gfa values file (if generated)")
	qa = File(desc="path/name of along tract qa values file (if generated)")
	nqa = File(desc="path/name of along tract nqa values file (if generated)")
	md = File(desc="path/name of along tract md values file (if generated)")
	ad = File(desc="path/name of along tract ad values file (if generated)")
	rd = File(desc="path/name of along tract rd values file (if generated)")
	report_fa = File(desc="path/name of tract report fa values file "
						  "(if generated)")
	report_gfa = File(desc="path/name of tract report gfa values file "
						  "(if generated)")
	report_qa = File(desc="path/name of tract report qa values file "
						  "(if generated)")
	report_nqa = File(desc="path/name of tract report nqa values file "
						  "(if generated)")
	report_md = File(desc="path/name of tract report md values file "
						  "(if generated)")
	report_ad = File(desc="path/name of tract report ad values file "
						  "(if generated)")
	report_rd = File(desc="path/name of tract report rd values file "
						  "(if generated)")



class DSIStudioFiberCommand(DSIStudioCommand):
	"""Not used directly, provides region and post-processing commands for
	DSI Studio trk and ana actions.
	"""
	input_spec = DSIStudioFiberInputSpec

	def _add_region_actions(self, name, value):
		"""helper function for _format_arg, 
		will add region action inputs to input value
		
		Parameters
		----------
		name : str (input name, e.g. 'seed', 'roi', 'roa', 'end', 'ter')
		value : str (region name or path, not the whole list)
		
		Returns
		-------
		newval : str (region name or path, with appended action options)

		Example
		-------
		trk=Node(interface=DSIStudioTrack())
		trk.inputs.roi=['ROI1.nii','ROI2.nii']
		trk.inputs.roi_action=[['dilation'],['dilation','smoothing']]
		trk.inputs.cmdline
		'dsi_studio --action=trk --roi=ROI1.nii,dilation --roi2=ROI2.nii,dilation,smoothing'
		"""
				
		actions = getattr(self.inputs, name+"_action")#matching action values
		wholevalue = getattr(self.inputs, name)
		vi = wholevalue.index(value)
		if isdefined(actions) and \
			len(actions) != len(wholevalue):
			raise AttributeError("N Entries in %s action list does not match"
								 "N Regions" % name)
		
		action_ts = self.inputs.trait(name+"_action")#matching action specific
		modval = []
		modval.append(value)
		newval = value #return input if there are no region actions
		if isdefined(actions):
			if isdefined(action_ts.sep):
				sep = action_ts.sep
			else:
				sep = ','
				for e in actions[vi]:
					if e:#if not an empty list
						modval.append(sep)
						modval.append(e)
					else:#if an empty list
						continue
			newval = ''.join(modval)
		return newval

	def _format_arg(self, name, trait_spec, value):
		"""alternative helper function for _parse_inputs, 
		format roi, roa, end, seed, ter, export, atlas argstrs
		
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
		#print argstr #debug
		sep = trait_spec.sep if trait_spec.sep is not None else ' '

		if name == "roi" or \
			name == "roa" or \
			name == "end" or \
			name == "seed" or \
			name =="ter":
		#--roi=1 --roi2=2 --roi3=3, same pattern for all regions
			arglist = []
			#InputMultiPath is a traits.List
			if isdefined(self.inputs.name):
				if isinstance(self.inputs.name, InputMultiPath):
					#--roiX=region
					argstrfixed = argstr
					if not isdefined(self.inputs.atlas):
						atlas = ''
					else:
						atlas = self.inputs.atlas
				else:
					#if atlas is defined is checked automatically with
					#requires=["atlas"] in inputspec
					#--roiX=atlas:region
					argstrfixed = argstr.replace('=','=%s:')
			for e in value:
				#_add_region_actions() returns e if no actions
				ewactions = self._add_region_actions(name, e)
				i = value.index(e)
				if i == 0:
					roin = ''
				elif name == "roi" and i > 4:
					print("Cannot have more than 5 rois, first 5 will be used")
					break
				elif name == "end" and i > 1:
					print("Cannot have more than 2 ends, first 2 will be used")
					break
				else:
					roin = i + 1
				arglist.append(argstrfixed % (roin, atlas, ewactions))
			return sep.join(arglist)
			
		elif name == "export": #report vals should not be parsed normally
			for e in value:
				if e == "report" and \
				self.inputs.report_val is not None and \
				self.inputs.report_pstyle is not None and \
				self.inputs.report_bandwidth is not None:
					newe = []
					newe.append(e)
					newe.append(":")
					newe.append(self.inputs.report_val)
					newe.append(":")
					newe.append(str(self.inputs.report_pstyle))
					newe.append(":")
					newe.append(str(self.inputs.report_bandwidth))
					i = value.index(e)
			value[i] = "".join(str(newe))
			return argstr % sep.join(str(e) for e in value)
			
		elif name == "connectivity":
			if len(value)==len(self.inputs.connectivity_type) and \
			len(value)==len(self.inputs.connectivity_value):
				return super(DSIStudioFiberCommand, 
				self._format_arg(name, trait_spec, value))
			else:
				raise AttributeError("N inputs for connectivity, connectivity_"
				"type, connectivity_value must be equal")
		
		else:
			#print('Super: ' + argstr) #debug
			return super(DSIStudioFiberCommand, 
			self)._format_arg(name, trait_spec, value)

	def _gen_filename(self, name):
		if name == "track":
			_, filename, _ = split_filename(
				os.path.abspath(self.inputs.source))
			fname = []
			fname.append(filename)
			fname.append("_track")
			fname.append(Info.output_type_to_ext(self.inputs.output_type))
			return "".join(fname)
		else:
			return super(DSIStudioFiberCommand, self)._gen_filename(name)

	def _parse_inputs(self, skip=None):
		deftoskip = ["report_val",
					"report_pstyle",
					"report_bandwidth",
					"seed_action",
					"roi_action",
					"roa_action",
					"end_action",
					"ter_action"]
		if skip is None:
			toskip = deftoskip
		else:
			toskip = []
			for e in skip:
				toskip.append(e)
			for e in deftoskip:
				toskip.append(e)
		return super(DSIStudioFiberCommand, self)._parse_inputs(skip=toskip)



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
	
	def _list_outputs(self):
		outputs = self._outputs().get()
		tractdir = os.path.join(os.getcwd(),"Tracts")
		if isdefined(self.inputs.output):
			outputs["track"] = self.inputs.output
		else:
			outputs["track"] = self._gen_fname("track", cwd=tractdir)
		
		if isdefined(self.inputs.export):
			outputs["export"] = self.inputs.export



class DSIStudioAnalysisInputSpec(DSIStudioFiberInputSpec):

	output_type = traits.Enum("TXT", "TRK", "NIFTI",
		usedefault=True,
		desc="DSI Studio ana action output type")
	#if more than 1 roi is given, or track is specified, DSIstudio will
	#do tract analysis, else region analysis
	track = File(exists=True, 
		argstr="--tract=%s",
		desc="assign tract file for analysis")
	



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
	'dsi_studio --action=ana --source=my.fib.gz --tract=myTract.trk.gz --output=myTract.txt --export=stat'
	"""
	_action = "ana"
	_output_type = "TXT"
	input_spec = DSIStudioAnalysisInputSpec
	output_spec = DSIStudioFiberOutputSpec



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
	
	output = File(exists=True,
		desc="DSI Studio src file")



class DSIStudioSource(DSIStudioCommand):
	"""DSI Studio SRC action support
	"""
	_action = "src"
	_output_type = "SRC"
	input_spec = DSIStudioSourceInputSpec
	output_spec = DSIStudioSourceOutputSpec

	def _gen_filename(self, name):
		if name == "output":
			_, filename, _ = split_filename(
				os.path.abspath(self.inputs.source))
			fname = []
			fname.append(filename)
			fname.append(Info.output_type_to_ext(self.inputs.output_type))
			return "".join(fname)
		else:
			return super(DSIStudioSource, self)._gen_filename(name)



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
		argstr="--method=0",
		xor=["method_dti","method_frqbi","method_shqbi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=['check_btable','hanning_filter_width'],
		desc="assign DSI method for reconstruction")
	method_dti = traits.Bool(
		argstr="--method=1",
		xor=["method_dsi","method_frqbi","method_shqbi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=['check_btable','output_dif','output_tensor'],
		desc="assign DTI method for reconstruction")
	method_frqbi = traits.Bool(
		argstr="--method=2",
		xor=["method_dti","method_dsi","method_shqbi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=['check_btable','interp_kernel_width','smooth_kernel_width',
				'odf_order','record_odf','num_fiber'],
		desc="assign Funk-Radon QBI method for reconstruction")
	method_shqbi = traits.Bool(
		argstr="--method=3",
		xor=["method_dti","method_frqbi","method_dsi","method_gqi",
			"method_hardi","method_qsdr"],
		requires=['check_btable','harmonic_order','regularization',
				'odf_order','record_odf','num_fiber'],
		desc="assign Spherical Harmonic QBI method for reconstruction")
	method_gqi = traits.Bool(
		argstr="--method=4",
		xor=["method_dti","method_frqbi","method_shqbi","method_dsi",
			"method_hardi","method_qsdr"],
		requires=['check_btable','mddr','r2_weighted','output_rdi',
				'odf_order','record_odf','num_fiber'],
		desc="assign GQI method for reconstruction")
	method_hardi = traits.Bool(
		argstr="--method=6",
		xor=["method_dti","method_frqbi","method_shqbi","method_gqi",
			"method_dsi","method_qsdr"],
		requires=['check_btable','mddr','regularization','b_value','num_fiber'],
		desc="Convert to HARDI")
	method_qsdr = traits.Bool(
		argstr="--method=7",
		xor=["method_dti","method_frqbi","method_shqbi","method_gqi",
			"method_hardi","method_dsi"],
		requires=['check_btable','mddr','regularization','r2_weighted',
				'output_resolution','output_mapping','output_jac','output_rdi',
				'odf_order','record_odf','other_image','csf_cal',
				'interpolation','regist_method','num_fiber'],
		desc="assign QSDR method for reconstruction")
							
	method = traits.Enum(1,0,2,3,4,6,7, 
		mandatory=True, 
		argstr="--method=%d",
		desc="Reconstruction method, 0:DSI, 1:DTI, 2:Funk-Randon QBI, "
			"3:Spherical Harmonic QBI, 4:GQI, 6:Convert to HARDI, 7:QSDR")

	#params includes some floats, some ints depending on method
	#they've been split by method for xor and requires checks
	params = traits.List(
		argstr="--param%s=%s",
		desc="Reconstruction parameters, different meaning and types for "
			"different methods")
	param0 = traits.Float(desc="param 0 for method")
	param1 = traits.Float(desc="param 1 for method")
	param2 = traits.Float(desc="param 2 for method")
	param3 = traits.Float(desc="param 3 for method")
	param4 = traits.Float(desc="param 4 for method")
	
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
		desc="QSDR - output resolution in mm")#--other_image=t1w,/directory/my_t1w.nii.gz;t2w,/directory/my_t1w.nii.gz
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
	#TODO adjust params for deconv, decomp
	deconvolution = traits.Enum(0,1, 
		usedefault=True,
		argstr="--deconvolution=%d",
		desc="whether to apply deconvolution")
	decomposition = traits.Enum(0,1, 
		usedefault=True,
		argstr="--decomposition=%d",
		requires=['decomp_frac','m_value'],
		desc="whether to apply decomposition")
	decomp_frac = traits.Float(0.05,
		usedefault=True,
		desc="decomposition fraction")
	m_value = traits.Int(10,
		usedefault=True,
		desc="decomposition m value")
	regist_method = traits.Enum(0,1,2,3,4, 
		usedefault=True,
		argstr="--reg_method=%d",
		desc="QSDR - registration method 0:SPM 7-9-7, 1:SPM 14-18-14, "
			"2:SPM 21-27-21, 3:CDM, 4:T1W-CDM")
	t1w = File(exists=True, 
		argstr="--t1w=%s", 
		requires=["reg_method"],
		desc="QSDR - assign a t1w file for registration method 4")
	



class DSIStudioReconstructOutputSpec(DSIStudioOutputSpec):
	"""DSI Studio reconstruct output specification"""
	fiber_file = File(exists=True, desc="Fiber tracking file")
	#filename depends on reconstruction method, and automatic detections by
	#DSIStudio, unsure how to tell nipype workflow about all of it
#Decoding the file extension
#The FIB file generated during the reconstruction will include several extension. Here is a list of the explanation
#odf8: An 8-fold ODF tessellation was used
#f5: For each voxel, a maximum of 5 fiber directions were resolved
#rec: ODF information was output in the FIB file
#csfc: quantitative diffusion MRI was conducted using CSF location as the free water calibration
#hs: A half sphere scheme was used to acquired DSI
#reg0i2: the spatial normalization was conducted using (reg0: 7-9-7 reg1: 14-18-14 reg2: 21-27-21) and the images were interpolated using (i0: trilinear interpolation, I1: Guassian radial basis i2: cubic spine)
#bal: The diffusion scheme was resampled to ensure balance in the 3D space
#fx, fy, fz: The b-table was automatically flipped by DSI Studio in x-, y-, or z- direction. 012 means the order of the x-y-z coordinates is the same, whereas 102 indicates x-y flip, 210 x-z flip, and 021 y-z- flip. 
#rdi: The restricted diffusioin imaging metrics were calculated 
#de: deconvolution was used to sharpen the ODF
#dec: decomposition was used to sharpen the ODF
#gqi: The images were reconstructed using generalized q-sampling imaging
#qsdr: The images were reconstructed using q-space diffeomorphic reconstruction
#R72: The goodness-of-fit between the subject's data and the template has a R-squared value of 0.72


class DSIStudioReconstruct(DSIStudioCommand):
	"""DSI Studio reconstruct action support
	TESTING
	"""
	nparams=dict()
	_action = "rec"
	_output_type = "FIB"
	input_spec = DSIStudioReconstructInputSpec
	output_spec = DSIStudioReconstructOutputSpec
	
	def _check_mandatory_inputs(self):
		"""using this to insert necessary values, will also return an exception 
		if a mandatory input is Undefined
		"""
		for name, spec in self.inputs.traits(mandatory=True).items():
			value = getattr(self.inputs, name)

            #insert values
			if name == "method":
				if isdefined(self.inputs.method):
					if value == 0:
						self.inputs.method_dsi = True
						fix = self.inputs.trait('method_dsi')
					elif value == 1:
						self.inputs.method_dti = True
						fix = self.inputs.trait('method_dti')
					elif value == 2:
						self.inputs.method_frqbi = True
						fix = self.inputs.trait('method_frqbi')
					if value == 3:
						self.inputs.method_shqbi = True
						fix = self.inputs.trait('method_shqbi')
					elif value == 4:
						self.inputs.method_gqi = True
						fix = self.inputs.trait('method_gqi')
					elif value == 6:
						self.inputs.method_hardi = True
						fix = self.inputs.trait('method_hardi')
					elif value == 7:
						self.inputs.method_qsdr = True
						fix = self.inputs.trait('method_qsdr')
					for x in fix.xor:
						setattr(self.inputs, x, _Undefined())
				else:
					if isdefined(self.inputs.method_dsi) and \
					self.inputs.method_dsi == True:
						self.inputs.method = 0
					if isdefined(self.inputs.method_dti) and \
					self.inputs.method_dti == True:
						self.inputs.method = 1
					if isdefined(self.inputs.method_frqbi) and \
					self.inputs.method_frqbi == True:
						self.inputs.method = 2
					if isdefined(self.inputs.method_shqbi) and \
					self.inputs.method_shqbi == True:
						self.inputs.method = 3
					if isdefined(self.inputs.method_gqi) and \
					self.inputs.method_gqi == True:
						self.inputs.method = 4
					if isdefined(self.inputs.method_hardi) and \
					self.inputs.method_hardi == True:
						self.inputs.method = 6
					if isdefined(self.inputs.method_qsdr) and \
					self.inputs.method_qsdr == True:
						self.inputs.method = 7
			
			if name == "params":
				pass
            
			self._check_xor(spec, name, value)
			if not isdefined(value) and spec.xor is None:
				msg = ("%s requires a value for input '%s'. "
					"For a list of required inputs, see %s.help()" %
					(self.__class__.__name__, name, self.__class__.__name__))
				raise ValueError(msg)
			if isdefined(value):
				self._check_requires(spec, name, value)
		for name, spec in self.inputs.traits(mandatory=None,
											transient=None).items():
			self._check_requires(spec, name, getattr(self.inputs, name))

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
		print argstr #debug
		sep = trait_spec.sep if trait_spec.sep is not None else " "
		arglist = []
			
		#TODO pull params from other variables if not defined directly
		if name == "params":
			#method should be defined, parsed in alphabetical order
			recmethodid = Info.rec_method_n_to_id(self.inputs.method)
			expnparams = Info.rec_method_to_nparams(recmethodid)
			expparamtypes = Info.rec_method_to_param_types(recmethodid)
			if recmethodid == "DTI":
				pass #no params
			
			if len(value) == expnparams:
				for e in value:
					if isinstance(e, Info.rec_method_to_param_types(
						recmethodid)[value.index(e)]):
						#numbered from 0
						arglist.append(argstr % (value.index(e),e))
					else:
						raise AttributeError("Param type: %s != Expected "
							"Param type: %s for Param: %s, in Method: %s" %
							(type(e),expparamtypes[value.index(e)],e,
							recmethodid))
				return sep.join(arglist)
			else:
				raise AttributeError("N input params: '%d' != "
									"Expected N params: '%d' for Method: %s" %
									(len(value),expnparams,recmethodid))
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

	def _parse_inputs(self, skip=None):
		#super._parse_inputs any var with an argstr will be parsed if not in skip
		#up
		methodskips = ["method_dsi","method_dti","method_frqbi","method_shqbi",
		"method_gqi","method_hardi","method_qsdr"]
		oiskips = ["other_image_type","other_image_file"]
		if skip is None:
			toskip = deftoskip
		else:
			toskip = []
			for e in skip:
				toskip.append(e)
			for e in deftoskip:
				toskip.append(e)
		return super(DSIStudioReconstruct, self)._parse_inputs(skip=toskip)



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
	INCOMPLETE
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
			erv = []
			erv.append(source)
			erv.append(value[value.index(e)]) #DSI Studio adds export target to ext
			erv.append(Info.output_type_to_ext(self.inputs.output_type))
			rvunjoined.append(erv)
		for e in rvunjoined:
			retval.append("".join(e))
		return retval

