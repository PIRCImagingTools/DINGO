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
	roi = InputMultiPath(File(exists=True), argstr="--roi%s=%s",
						 desc="roi files through which tracts must pass")
	roa = InputMultiPath(File(exists=True), argstr="--roa%s=%s",
						 desc="roa files which tracts must avoid")
	end = InputMultiPath(File(exists=True), argstr="--end%s=%s",
			   			 desc="filter out tracks that do not end in this region")
	ter = File(exists=True,
			   argstr="--ter=%s",
			   desc="terminates any track that enters this region")
	t1t2 = File(exists=True,
				argstr="--t1t2=%s",
				desc="specify t1w or t2w images as roi reference image")
	atlas = traits.List(
		traits.Enum("aal", "ATAG_basal_ganglia", "brodmann", "Cerebellum-SUIT",
					"FreeSurferDKT", "Gordan_rsfMRI333", "HarvardOxfordCort",
					"HarvardOxfordSub","HCP-MMP1","JHU-WhiteMatter-labels-1mm",
					"MNI", "OASIS_TRT_20", "sri24_tissues","sri24_tzo116plus",
					"talairach","tractography"),
		argstr="--atlas=%s", sep=",")
	
	#Post-Process Parameters
	delete_repeat = traits.Enum(0,1, argstr="--delete_repeat=%d",
								desc="0 or 1, 1 removes repeat tracks with"
									"distance < 1 mm")
	output = File(genfile=True,
				  argstr="--output=%s",
				  desc="output tract file name, "
					   "format may be txt, trk, or nii")
	end_point = File(genfile=True,
					 argstr="--end_point=%s",
					 desc="endpoint file name, format may be txt or mat")
	export = traits.List(
		traits.Enum("stat","tdi","tdi2","tdi_color","tdi_end","tdi2_end",
					"fa","gfa","qa","nqa","md","ad","rd","report"),
						 argstr="--export=%s", sep=',',
						 desc="export information related to fiber tracts")
	report_val = traits.Enum("fa","gfa","qa","nqa","md","ad","rd",
							 argstr=":%s",
							 desc="type of values for tract report")
	report_pstyle = traits.Enum(0,1,2,3,4, argstr=":%d",
								requires=["export"],
								desc="profile style for tract report "
									 "0:x, 1:y, 2:z, 3:along tracts, "
									 "4:tract mean")
	report_bandwidth = traits.Float(1.0, argstr=":%.1f",
									requires=["export"],
									desc="bandwidth for tract report")



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

	def _format_arg(self, name, trait_spec, value):
		"""alternative helper function for _parse_inputs"""

		argstr = trait_spec.argstr
		print argstr
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
			report_pstyle = self.inputs.report_pstyle
			report_bandwidth = self.inputs.report_bandwidth
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
			return super(DSIStudioFiberCommand, self)._format_arg(name, trait_spec, value)


	def _parse_inputs(self, skip=None):
		if skip is None:
			toskip = ["report_val","report_pstyle","report_bandwidth"]
		else:
			toskip = []
			for e in skip:
				toskip.append(e)
			toskip.append("report_val")
			toskip.append("report_pstyle")
			toskip.append("report_bandwidth")
		return super(DSIStudioFiberCommand, self)._parse_inputs(skip=toskip)



class DSIStudioTrackInputSpec(DSIStudioFiberInputSpec):
	"""Input specification for DSI Studio fiber tracking"""
	action = traits.Enum("trk", mandatory=True, desc="DSI Studio action type")
	output_type = traits.Enum("TRK", desc="DSI Studio trk action output type")
	method = traits.Enum(0, 1, argstr="--method=%d",
						 desc="0:streamline (default), 1:rk4")
	fiber_count = traits.Int(5000, argstr="--fiber_count=%d",
							 desc="number of fiber tracks to find, "
								  "end criterion")
	seed_count = traits.Int(1000000, argstr="--seed_count=%d",
							desc="max number of seeds, end criterion")
	fa_threshold = traits.Float(0.1, argstr="--fa_threshold=%.4f",
								desc="")
	threshold_index = traits.Str(argstr="--threshold_index=%s",
								 requires=["fa_threshold"], 
								 desc="")
	initial_dir = traits.Enum(0,1,2, argstr="--initial_dir=%d",
							  desc="initial propagation direction, "
								   "0:primary fiber (default),"
								   "1:random, 2:all fiber orientations")
	seed_plan = traits.Enum(0,1, argstr="--seed_plan=%d",
							desc="seeding strategy, 0:subvoxel random(default)"
								 "1:voxelwise center")
	interpolation = traits.Enum(0,1,2, argstr="--interpolation=%d",
								desc="interpolation method, 0:trilinear, "
									 "1:gaussian radial, 2:nearest neighbor")
	thread_count = traits.Int(2, argstr="--thread_count=%d",
							  desc="")
	random_seed = traits.Enum(0,1, argstr="--random_seed=%d",
							  desc="whether a timer is used to generate seed "
								   "points, default is off")
	step_size = traits.Float(argstr="--step_size=%.2f",
							 desc="moving distance in each tracking interval, "
								  "default is half the spatial resolution, mm")
	turning_angle = traits.Int(60, argstr="--turning_angle=%d",
							   desc="")
	#interpo_angle = traits.Int(60, argstr="--interpo_angle=%d", desc="")
	smoothing = traits.Float(0.00, argstr="--smoothing=%.2f", 
							 desc="fiber track momentum")
	min_length = traits.Int(15, argstr="--min_length=%d",
							desc="tracks below mm length deleted")
	max_length = traits.Int(500, argstr="--max_length=%d",
							desc="tracks above mm length deleted")

		

class DSIStudioTrack(DSIStudioCommand):
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

	def _gen_filename(self, tract):
		path, filename, ext = split_filename(
			os.path.abspath(self.inputs.source))
		fname = []
		fname.append(filename)
		fname.append("_")
		fname.append(tract)
		fname.append(Info.output_type_to_ext(self.inputs.output_type))
		return "".join(fname)
	
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
	action = traits.Enum("ana", mandatory=True, desc="DSI Studio action type")
	output_type = traits.Enum("TXT", desc="DSI Studio ana action output type")



class DSIStudioAnalysis(DSIStudioCommand):
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

	
