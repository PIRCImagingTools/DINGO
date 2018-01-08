from nipype.interfaces.base import (traits, File, InputMultiPath, isdefined, 
									CommandLine, CommandLineInputSpec, 
									TraitedSpec)
import os
from nipype.utils.filemanip import fname_presuffix, split_filename



class Info(object):
	#file extensions for output types
	ftypes = {'SRC': '.src.gz',
		  'FIB': '.fib.gz',
		  'NIFTI': '.nii.gz',
		  'TRK': '.trk.gz',
		  'TXT': '.txt'}

	#primary output types for action types
	act_out = {'trk': 'TRK',
		   'rec': 'FIB',
		   'src': 'SRC',
		   'ana': 'TXT'}

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



class DSIStudioInputSpec(CommandLineInputSpec):
	"""Base input specification for DSI Studio commands."""

	action = traits.Enum("trk","ana",
						 "src","rec","atl","exp","cnt","vis","ren",
						 argstr="--action=%s",
						 mandatory=True,
						 desc="Command action type to execute",
						 position=1)
	source = File(exists=True,
				  mandatory=True,
				  argstr="--source=%s",
				  desc="Input file to process",
				  position=2)
	


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
		fname = fname_presuffix(basename, suffix=suffix, use_ext=False,
								newpath=cwd)
		return fname

				  


class DSIStudioFiberInputSpec(DSIStudioInputSpec):
	"""Provides region and post-processing input
	specification used with DSI Studio trk and ana actions.
	"""
	#ROI Parameters
	seed = File(exists=True,
				argstr="--seed=%s",
				desc="specify seeding file, txt, analyze, or nifti, "
					 "unspecified default is whole brain")
	#DSI Studio has built in accepted values that are not file paths,
	#but AtlasName:RegionName
	roi = InputMultiPath(File(exists=True), 
						argstr="--roi%s=%s",
						desc="roi files through which tracts must pass, "
							"txt, analyze, or nifti")
	roi_action = traits.List(traits.Enum("smoothing","erosion","dilation",
										"defragment","negate","flipx","flipy",
										"flipz"),
							requires = ["roi"],
							argstr="%s",
							sep=",",
							desc="action codes to modify rois, "
							"list for each roi")
	roa = InputMultiPath(File(exists=True), 
						argstr="--roa%s=%s",
						desc="roa files which tracts must avoid, "
							"txt, analyze, or nifti")
	roa_action = traits.List(traits.Enum("smoothing","erosion","dilation",
										"defragment","negate","flipx","flipy",
										"flipz"),
							requires = ["roa"],
							argstr="%s",
							sep=",",
							desc="action codes to modify roas, "
							"list for each roa")
	end = InputMultiPath(File(exists=True), 
						argstr="--end%s=%s",
			   			desc="filter out tracks that do not end in this "
							"region, txt, analyze, or nifti")
	end_action = traits.List(traits.Enum("smoothing","erosion","dilation",
										"defragment","negate","flipx","flipy",
										"flipz"),
							requires = ["end"],
							argstr="%s",
							sep=",",
							desc="action codes to modify ends, "
							"list for each end")
	ter = File(exists=True,
			   argstr="--ter=%s",
			   desc="terminates any track that enters this region, "
							"txt, analyze, or nifti")
	ter_action = traits.List(traits.Enum("smoothing","erosion","dilation",
										"defragment","negate","flipx","flipy",
										"flipz"),
							requires = ["ter"],
							argstr="%s",
							sep=",",
							desc="action codes to modify terminative region")
	t1t2 = File(exists=True,
				argstr="--t1t2=%s",
				desc="specify t1w or t2w images as roi reference image")
	atlas = traits.List(
		traits.Enum("aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
					"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
					"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
					"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
					"talairach","tractography"),
		argstr="--atlas=%s", 
		sep=",")
	
	#Post-Process Parameters
	delete_repeat = traits.Enum(0,1, 
								argstr="--delete_repeat=%d",
								desc="0 or 1, 1 removes repeat tracks with"
									"distance < 1 mm")
	output = File(genfile=True,
				  argstr="--output=%s",
				  hash_files=False,
				  desc="output tract file name, "
					   "format may be txt, trk, or nii")
	end_point = File(argstr="--end_point=%s",
					 hash_files=False,
					 desc="endpoint file name, format may be txt or mat")
	export = traits.List(
		traits.Enum("stat","tdi","tdi2","tdi_color","tdi_end","tdi2_end",
					"fa","gfa","qa","nqa","md","ad","rd","report"),
					argstr="--export=%s", 
					sep=',',
					desc="export information related to fiber tracts")
	report_val = traits.Enum("fa","gfa","qa","nqa","md","ad","rd",
							 argstr=":%s",
							 desc="type of values for tract report")
	report_pstyle = traits.Enum(0,1,2,3,4, 
								argstr=":%d",
								requires=["export"],
								desc="profile style for tract report "
									 "0:x, 1:y, 2:z, 3:along tracts, "
									 "4:tract mean")
	report_bandwidth = traits.Float(1.0, 
									argstr=":%.1f",
									requires=["export"],
									desc="bandwidth for tract report")
	connectivity = traits.Str(atlas,
							argstr="--connectivity=%s",
							desc="atlas id(s), or path to MNI space roi file")
	connectivity_type = traits.List(traits.Enum("end","pass"),
								argstr="--connectivity_type=%s",
								requires=["connectivity"],
								desc="method to count the tracts, default end")
	connectivity_value = traits.List(traits.Str(argstr="%s"),
							argstr="--connectivity_value=%s",
							sep=",",
							requires=["connectivity"],
							desc="method to calculate connectivity matrix, "
								"default count - n tracks pass/end in region, "
								"ncount - n tracks norm by median length, "
								"mean_length - outputs mean length of tracks, "
								"trk - outputs trk file each matrix entry, "
								"other values by reconstruction method, "
								"e.g. 'fa','qa','adc', etc.")
	connectivity_threshold = traits.Float(0.001,
				argstr="--connectivity_threshold=%.3f",
				requires=["connectivity"],
				desc="threshold for calculating binarized graph measures and "
					"connectivity values, def 0.001, i.e. if the max "
					"connectivity count is 1000 tracks in the connectivity "
					"matrix, then at least 1000 x 0.001 = 1 track is needed to"
					" pass the threshold, otherwise values will be 0")
	ref = File(exists=True,
				argstr="--ref=%s",
				desc="output track coordinate based on a reference image, "
					"e.g. T1w or T2w")



class DSIStudioFiberOutputSpec(DSIStudioInputSpec):
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

	def _format_region_actions(self, name, trait_spec, value):
		foo = ""
		return foo

	def _format_arg(self, name, trait_spec, value):
		"""alternative helper function for _parse_inputs, 
		format roi, roa, end, export, atlas argstrs
		"""

		argstr = trait_spec.argstr
		print argstr #debug
		sep = trait_spec.sep if trait_spec.sep is not None else ' '

		if name == "roi" or name == "roa" or name == "end":
		#--roi=1 --roi2=2 --roi3=3
			arglist = []
			for e in value:
				if value.index(e) == 0:
					arglist.append(argstr % ('',e))
				elif name == "roi" and value.index(e) > 4:
					print("Cannot have more than 5 rois, first 5 will be used")
					break
				elif name == "end" and value.index(e) > 1:
					print("Cannot have more than 2 ends, first 2 will be used")
					break
				else:
					arglist.append(argstr % (value.index(e)+1,e))
			return sep.join(arglist)
		elif name == "export": #report vals should not be parsed normally
			for e in value:
				if (e == "report" and 
				self.inputs.report_val is not None and 
				self.inputs.report_pstyle is not None and 
				self.inputs.report_bandwidth is not None):
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
		else:
			print('Super: ' + argstr)
			return super(DSIStudioFiberCommand, self)._format_arg(name, trait_spec, value)

	def _gen_filename(self, name):
		if name == "output":
			path, filename, ext = split_filename(
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

	output_type = traits.Enum("TRK", 
							usedefault=True,
							desc="DSI Studio trk action output type")
	method = traits.Enum(0, 1, 
						argstr="--method=%d",
						usedefault=True,
						desc="0:streamline (default), 1:rk4")
	fiber_count = traits.Int(5000, 
							argstr="--fiber_count=%d",
							usedefault=True,
							desc="number of fiber tracks to find, "
								  "end criterion")
	seed_count = traits.Int(1000000, 
							argstr="--seed_count=%d",
							usedefault=True,
							desc="max number of seeds, end criterion")
	fa_threshold = traits.Float(0.1, 
								argstr="--fa_threshold=%.4f",
								usedefault=True,
								desc="")
	threshold_index = traits.Str(argstr="--threshold_index=%s",
								 requires=["fa_threshold"], 
								 desc="assign threshold to another index")
	initial_dir = traits.Enum(0,1,2, 
							argstr="--initial_dir=%d",
							desc="initial propagation direction, "
								   "0:primary fiber (default),"
								   "1:random, 2:all fiber orientations")
	seed_plan = traits.Enum(0,1, 
							argstr="--seed_plan=%d",
							desc="seeding strategy, 0:subvoxel random(default)"
								 "1:voxelwise center")
	interpolation = traits.Enum(0,1,2, 
								argstr="--interpolation=%d",
								desc="interpolation method, 0:trilinear, "
									 "1:gaussian radial, 2:nearest neighbor")
	thread_count = traits.Int(2, 
							argstr="--thread_count=%d",
							desc="Assign number of threads to use")
	random_seed = traits.Enum(0,1, 
							argstr="--random_seed=%d",
							desc="whether a timer is used to generate seed "
								   "points, default is off")
	step_size = traits.Float(0.5,
							argstr="--step_size=%.2f",
							usedefault=True,
							desc="moving distance in each tracking interval, "
								  "default is half the spatial resolution, mm")
	turning_angle = traits.Int(60, 
							argstr="--turning_angle=%d",
							usedefault=True,
							 desc="")
	#listed on website, but didn't seem to be in code, and I don't know
	#what it's supposed to do - leaving out should get default
	#interpo_angle = traits.Int(60, argstr="--interpo_angle=%d", desc="")
	smoothing = traits.Float(0.20, 
							argstr="--smoothing=%.2f", 
							usedefault=True,
							desc="fiber track momentum")
	min_length = traits.Int(15, 
							argstr="--min_length=%d",
							usedefault=True,
							desc="tracks below mm length deleted")
	max_length = traits.Int(400, 
							argstr="--max_length=%d",
							usedefault=True,
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

	output_type = traits.Enum("TXT", 
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
	input_spec = DSIStudioAnalysisInputSpec
	output_spec = DSIStudioFiberOutputSpec



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
	method = traits.Enum(1,0,2,3,4,6,7, 
						mandatory=True, 
						argstr="--method=%d",
						usedefault=True,
						desc="Reconstruction method, 0:DSI, 1:DTI, "
							"2:Funk-Randon QBI, 3:Spherical Harmonic QBI, "
							"4:GQI, 6:Convert to HARDI, 7:QSDR")
	params = traits.List(argstr="--param%s=%s",
						desc="Reconstruction parameters, different meaning"
							"and types for different methods")#some floats, some ints
	odf_order = traits.Enum(8,4,5,6,10,12,16,20, 
							argstr="--odf_order=%d",
							desc="tesselation number of the odf, default 8")
	num_fiber = traits.Int(5, argstr="--num_fiber=%d",
					desc="max count of resolving fibers per voxel, default 5")
	deconvolution = traits.Enum(0,1, 
								argstr="--deconvolution=%d",
								desc="whether to apply deconvolution")
	decomposition = traits.Enum(0,1, 
								argstr="--decomposition=%d",
								desc="whether to apply decomposition")
	r2_weighted = traits.Enum(0,1, 
						argstr="--r2_weighted=%d",
						desc="whether to apply r2 weighted GQI reconstruction")
	reg_method = traits.Enum(0,1,2,3,4, 
						argstr="--reg_method=%d",
						desc="regularization method in QSDR, 0:SPM 7-9-7, "
							"1:SPM 14-18-14, 2:SPM 21-27-21, 3:CDM, 4:T1W-CDM")
	t1w = File(exists=True, 
				argstr="--t1w=%s", 
				requires=["reg_method"],
				desc="assign a t1w file for qsdr regularization method 4")
	affine = File(exists=True, 
				argstr="--affine=%s",
				desc="text file containing a transformation matrix. "
					"e.g. the following shifts in x and y by 10 voxels: \n"
					"1 0 0 -10 \n 0 1 0 -10 \n 0 0 1 0")
	flip = traits.Int(argstr="--flip=%d", 
					desc="flip image volume and b-table. 0:flip x, 1:flip y, "
						"2:flip z, 3:flip xy, 4:flip yz, 5: flip xz. \n"
						"e.g. 301 performs flip xy, flip x, flip y")
	motion_corr = traits.Enum(0,1, 
					argstr="--motion_correction=%d",
					desc="whether to apply motion and eddy current correction,"
						" works only on DTI dataset")
	interpo_method = traits.Enum(0,1,2, 
			argstr="interpo_method=%d",
			desc="interpolation method used in QSDR, 0:trilinear, "
				"1:gaussian radial basis, 2:tricubic")
	check_btable = traits.Enum(1,0, 
					argstr="--check_btable=%d",
					usedefault=True,
					desc="whether to do b-table flipping, default yes")
	other_image = traits.Bool(argstr="--other_image=%s,%s",
					requires=["other_image_type","other_image_file"],
					desc="assign other image volume to be wrapped with QSDR.")
	other_image_type = traits.Enum("t1w","t2w",
					requires=["other_image","other_image_file"],
					desc="t1w or t2w (maybe others, but not set up for it)")
	other_image_file = File(exists=True, 
							requires=["other_image","other_image_type"],
							desc="filepath for image to be wrapped with QSDR")
	output_mapping = traits.Enum(0,1, 
						argstr="--output_mapping=%d",
						usedefault=True,
						desc="used in QSDR to output mapping for each voxel, "
							"default 0")
	output_jac = traits.Enum(0,1, argstr="--output_jac=%d",
					usedefault=True,
					desc="used in QSDR to output jacobian determinant, "
						"default 0")
	output_dif = traits.Enum(1,0, 
					argstr="--output_dif=%d",
					usedefault=True,
					desc="used in DTI to output diffusivity, default 1")
	output_tensor = traits.Enum(1,0, 
					argstr="--output_tensor=%d",
					usedefault=True,
					desc="used in DTI to output whole tensor, default 1")
	output_rdi = traits.Enum(1,0, 
					argstr="--output_rdi=%d",
					usedefault=True,
					desc="used in GQI, QSDR to output restricted diffusion "
						"imaging, default 1")
	record_odf = traits.Enum(0,1, 
					argstr="--record_odf=%d",
					desc="whether to output ODF for connectometry analysis")
	csf_cal = traits.Enum(1,0, 
				argstr="--csf_calibration=%d",
				usedefault=True,
				desc="used in GQI, QSDR to enable CSF calibration, default 1")



class DSIStudioReconstructOutputSpec(TraitedSpec):
	"""DSI Studio reconstruct output specification"""
	fiber_file = File(exists=True, desc="Fiber tracking file")
	#filename seems to depend on reconstruction method, but unsure of the details


#INCOMPLETE
class DSIStudioReconstruct(DSIStudioCommand):
	"""DSI Studio reconstruct action support

	INCOMPLETE
	"""
	_action = "rec"
	input_spec = DSIStudioReconstructInputSpec
	output_spec = DSIStudioReconstructOutputSpec

	def _format_arg(self, name, trait_spec, value):
		"""alternative helper function for _parse_inputs, 
		only include specific argstrs for the reconstruction method,
		format method specific argstrs, params, other_image_...,
		"""

		argstr = trait_spec.argstr
		print argstr #debug
		sep = trait_spec.sep if trait_spec.sep is not None else ' '

	def _parse_inputs(self, skip=None):
		deftoskip = ["other_image_type","other_image_file"]
		if skip is None:
			toskip = deftoskip
		else:
			toskip = []
			for e in skip:
				toskip.append(e)
			for e in deftoskip:
				toskip.append(e)
		return super(DSIStudioReconstruct, self)._parse_inputs(skip=toskip)
