from nipype import (IdentityInterface, Function)
from nipype.utils.misc import str2bool
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces.utility import Merge
from nipype.interfaces import fsl
import os
import logging
from DINGO.utils import (update_dict, read_config)
from DINGO.DSI_Studio_base import (DSIStudioSource, DSIStudioReconstruct, 
									DSIStudioTrack, DSIStudioAnalysis, 
									DSIStudioExport)
from DINGO.base import (DINGO, DINGOflow, DINGOnode)


class HelperDSI(DINGO):
	def __init__(self, **kwargs):
		wfm = {
			'DSI_SRC'	:	'DINGO.DSI_Studio',
			'REC_prep'	:	'DINGO.DSI_Studio',
			'DSI_REC'	:	'DINGO.DSI_Studio',
			'DSI_TRK'	:	'DINGO.DSI_Studio',
			'DSI_ANA'	:	'DINGO.DSI_Studio'
		}
		super(HelperDSI, self).__init__(workflow_to_module=wfm, **kwargs)

class DSI_SRC(DINGOnode):
	"""Nipype node to create a src file in DSIStudio with dwi, bval, bvec
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'DSI_SRC')
	inputs		:	Dict (Node InputName=ParameterValue)
	**kwargs	:	Workflow InputName=ParameterValue
					
	Returns
	-------
	Nipype node (name=name, interface=DSIStudioSource(**inputs), **kwargs)
	
	Example
	-------
	dsi_src = DSI_SRC(name='dsi_src',\
					inputs={'output' : 'mydtifile.nii.gz',\
							'bval' : 'mybvalfile.bval',\
							'bvec' : 'mybvecfile.bvec'},
					overwrite=False)
	dsi_src.outputs.output = mydtifile.src.gz
	"""
	
	connection_spec = {
		'source'		:	['EddyC','eddy_corrected'],
		'bval'			:	['FileIn','bval'],
		'bvec'			:	['FileIn','bvec']
	}
	
	def __init__(self, name="DSI_SRC", inputs=None, **kwargs):
		if inputs is None:
			inputs = {}
		super(DSI_SRC, self).__init__(
			name=name, 
			interface=DSIStudioSource(**inputs),
			**kwargs)
			
			
class REC_prep(DINGOnode):
	"""Nipype node to erode the BET mask (over-inclusive) to pass to DSI_REC"""

	connection_spec = {
		'in_file'		:	['BET','mask_file']
	}
	
	def __init__(self, name="REC_prep",\
	inputs=None, **kwargs):
		if inputs is None:
			inputs = {}
		if 'op_string' not in inputs:
			inputs['op_string'] = '-ero'
		if 'suffix' not in inputs:
			inputs['suffix'] = '_ero'
		rp = super(REC_prep, self).__init__(
			name=name, 
			interface=fsl.ImageMaths(**inputs),
			**kwargs)


class DSI_REC(DINGOnode):
	"""Nipype node to create a fib file in DSIStudio with src file
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'DSI_REC')
	inputs		:	Dict (REC node InputName=ParameterValue)
	**kwargs	:	Workflow InputName=ParameterValue
					
	Returns
	-------
	Nipype node (name=name, interface=DSIStudioReconstruct(**inputs), **kwargs)
	
	Example
	-------
	dsi_rec = DSI_REC(name='dsi_rec',
					inputs={'source' : 'mysrcfile.src.gz',\
							'mask' : 'mymaskfile.nii.gz',\
							'method' : 'dti'},
					overwrite=False)
	dsi_rec.outputs.fiber_file=mysrcfile.src.gz.dti.fib.gz
	"""
	
	connection_spec = {
		'source'		:	['DSI_SRC','output'],
		'mask'			:	['REC_prep','out_file']
	}

	def __init__(self, name="DSI_REC", inputs=None, **kwargs):
		if inputs is None:
			inputs = {}
		super(DSI_REC, self).__init__(
			name=name,
			interface=DSIStudioReconstruct(**inputs),
			**kwargs)
			
class TRKnode(pe.Node):
	"""Replace extended iterable parameterization with simpler based on
		just id and tract_name, not tract_inputs
	"""	
	def tract_name_dir(self, param):
		"""Return a reduced parameterization for output directory"""
		if '_tract_names' in param:
			return param[param.index('_tract_names'):]
		return param
			
	def output_dir(self):
		"""Return the location of the output directory with tract name, not tract inputs
		Mostly the same as nipype.pipeline.engine.Node.output_dir"""
		if self._output_dir:
			return self._output_dir
		
		if self.base_dir is None:
			self.base_dir = mkdtemp()
		outputdir = self.base_dir
		if self._hierarchy:
			outputdir = os.path.join(outputdir, *self._hierarchy.split('.'))
		if self.parameterization:
			params_str = ['{}'.format(p) for p in self.parameterization]
			params_str = [self.tract_name_dir(p) for p in params_str]
			if not str2bool(self.config['execution']['parameterize_dirs']):
				params_str = [_parameterization_dir(p) for p in params_str]
			outputdir = os.path.join(outputdir, *params_str)
			
		self._output_dir = os.path.abspath(os.path.join(outputdir, self.name))
		return self._output_dir	
		
class DSI_TRK(DINGOflow):
	"""Nipype wf to create a trk with fiber file and input parameters
	DSIStudioTrack.inputs will not seem to reflect the config until
	self._check_mandatory_inputs(), part of run() and cmdline(), is executed
	But, the data will be in the indict field.
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'DSI_TRK')
	inputs		:	Dict Track Node InputName=ParameterValue
		(Inputs['tracts'] is used specially as an iterable, other params
		will apply to each tract)
	**kwargs	:	Workflow InputName=ParameterValue
		any unspecified tracting parameters will be defaults of DSIStudioTrack
					
	Returns
	-------
	Nipype workflow
	
	Example
	-------
	dsi_trk = DSI_TRK(name='dsi_trk',\
					inputs={'source' : 'myfibfile.fib.gz',\
							'rois' : ['myROI1.nii.gz','myROI2.nii.gz'],\
							'roas' : ['myROA.nii.gz'],\
							'tract_name' : 'track'})
	dsi_trk.outputnode.outputs.tract_list = \
	os.path.abspath(myfibfile_track.nii.gz)
	"""
	from DSI_Studio import TRKnode
			
	_inputnode = 'inputnode'
	_outputnode = 'outputnode'
	
	connection_spec = {
		'fib_file'		:	['DSI_REC','fiber_file'],
		'regions'		:	['FileIn_SConfig','regions']
	}
	def __init__(self, name="DSI_TRK", inputs=None, **kwargs):
		if inputs is None:
			inputs = {}
		
		super(DSI_TRK, self).__init__(name=name, **kwargs)
		
		#Parse inputs
		inputnode = pe.Node(name='inputnode',
			interface=IdentityInterface(
				fields=[
					'fib_file',
					'tract_names', 
					'tract_inputs', 
					'regions']))
		
		if 'tracts' not in inputs:
			if 'rois' not in inputs:
				#config specifies no tracts
				raise KeyError('CANNOT TRACK! Neither "tracts" nor "rois" in '
				'inputs.')
			else:
				#config specifies one tract
				inputnode.inputs.tract_inputs = inputs
		else:
			#config specifies one or more tracts
			#Get universal params, but where overlap want to use tract specific
			univkeys = inputs.keys()
			univkeys.remove('tracts')
			universalinputs = { key : inputs[key] for key in univkeys }
			for tract in inputs['tracts'].iterkeys():
				for k,v in universalinputs.iteritems():
					if k not in inputs['tracts'][tract]:
						inputs['tracts'][tract].update({k:v})

			inputnode.iterables = [
				('tract_names', inputs['tracts'].keys()),
				('tract_inputs', inputs['tracts'].values())]
			inputnode.synchronize = True
		
		#Join tracts into list per subject
		outputjoinsource = []
		outputjoinsource.extend((name,'inputnode'))
		
		outputnode = pe.JoinNode(
			name="outputnode",
			interface=IdentityInterface(
				fields=["tract_list"]),
			joinsource='.'.join(outputjoinsource),
			joinfield="tract_list")
			
		#Substitute region names for actual region files
		replace_regions = TRKnode(
			name='replace_regions',
			interface=Function(
				input_names=['tract_input','regions'],
				output_names=['real_region_tract_input'],
				function=self.replace_regions))
		
		#DSI Studio will only accept 5 ROIs or 5 ROAs. A warning would normally 
		#be shown that only the first five listed will be used, but merging the 
		#ROAs is viable.
		merge_roas = self.create_merge_roas(name='merge_roas')

		trknode = TRKnode(
			name="trknode",
			interface=DSIStudioTrack())
			
		self.connect([
			(inputnode, trknode, 
				[('fib_file','source'),
				('tract_names','tract_name')]),
			(inputnode, replace_regions, 
				[('tract_inputs','tract_input'),
				('regions','regions')]),
			(replace_regions, merge_roas,
				[('real_region_tract_input', 'inputnode.tract_input')]),
			(merge_roas, trknode, 
				[('outputnode.mroa_tract_input','indict'),
				('outputnode.new_roa','roas')]),
			(trknode, outputnode, 
				[('track','tract_list')])
			])
			
	def replace_regions(tract_input=None, regions=None):
		"""Return the right regions needed by tract_input"""
		if regions is not None:
			#without per subject region list the analysis config must have
			#filepaths for region lists, can only do one subject
			##TODO eliminate alternatives, Sagittal_L breaks on ArcuateSagittal_L
			region_types = ('rois','roas','seed','ends','ter')
			for reg_type in region_types:
				if reg_type in tract_input:
					regionname_list = tract_input[reg_type]
					region_files = []
					for regionname in regionname_list:
						for realregion in regions:#realregion is a filepath
							if regionname in realregion:
								region_files.append(realregion)
								break
					tract_input.update({reg_type : region_files})
		return tract_input
								
	def create_merge_roas(self, name='merge_roas'):
		"""Create nipype workflow that will merge roas in tract_input"""
		merge = pe.Workflow(name=name)
		
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(
				fields=['tract_input']),
			mandatory_inputs=True)
			
		def separate_roas(tract_input):
			"""Function to split roas key from input dictionary, used as node"""
			#Unsure if nipype copies or passes dicts, to be safe returning it
			if 'roas' in tract_input and len(tract_input['roas']) > 5:
				roa_list = tract_input['roas']
				if not isinstance(roa_list, list):
					roa_list = [roa_list]
				del tract_input['roas']
			else:
				roa_list = None
			return tract_input, roa_list
			
		separate_roas = TRKnode(
			name='separate_roas',
			interface=Function(
				input_names=['tract_input'],
				output_names=['new_tract_input', 'roa_list'],
				function=separate_roas))
		
		mergenode = TRKnode(
			name='mergenode',
			interface=fsl.Merge(dimension='t'))
			
		maxnode = TRKnode(
			name='maxnode',
			interface=fsl.ImageMaths(op_string='-Tmax'))
			
		outputnode = pe.Node(
			name='outputnode',
			interface=IdentityInterface(
				fields=['mroa_tract_input', 'new_roa']))
				
		merge.connect([
			(inputnode, separate_roas, 
				[('tract_input', 'tract_input')]),
			(separate_roas, mergenode, 
				[('roa_list', 'in_files')]),
			(separate_roas, outputnode,
				[('new_tract_input','noroas_tract_input')]),
			(mergenode, maxnode, 
				[('merged_file', 'in_file')]),
			(maxnode, outputnode, 
				[('out_file', 'new_roa')])
			])
		
		return merge
		

class DSI_ANA(DINGOnode):
	"""Nipype node to run DSIStudioAnalysis
	
	Parameters
	----------
	name	:	Str (node name, default 'DSI_ANA')
	inputs	:	Dict (DSIStudioAnalysis Node InputName=ParameterValue)
	kwargs	:	(Nipype node InputName=ParameterValue)
	
	Returns
	-------
	Nipype node (name=name, interface=DSIStudioAnalysis(**inputs), **kwargs)
	
	Example
	-------
	dsi_ana = DSI_ANA(name='dsi_ana',
					inputs={'source' : 'my.fib.gz'
							'tract' : 'myTract.trk.gz'
							'output' : 'myTract.txt'
							'export' : 'stat'
					overwrite=False)
	dsi_ana.outputs.stat_file = myTract_stat.txt
	dsi_ana.outputs.track = myTract.txt
	"""
	def __init__(self, name='DSI_ANA', inputs={}, **kwargs):
		super(DSI_ANA, self).__init__(
			name=name,
			interface=DSIStudioAnalysis(**inputs),
			**kwargs)
			
			
class DSI_EXP(DINGOnode):
	"""Nipype node to run DSIStudioAnalysis
	
	Parameters
	----------
	name	:	Str (node name, default 'DSI_EXP')
	inputs	:	Dict (DSIStudioExport Node InputName=ParameterValue)
	kwargs	:	(Nipype node InputName=ParameterValue)
	
	Returns
	-------
	Nipype node (name=name, interface=DSIStudioExport(**inputs), **kwargs)
	
	Example
	-------
	dsi_exp = DSI_EXP(name='dsi_exp',
					inputs={'source' :	'my.fib.gz',\
							'export' : ['fa0'],\
							'output_type' : ['NIFTI']},
					overwrite=False)
	dsi_exp.outputs.export = [my.fib.gz.fa0.nii.gz]
	"""
	def __init__(self, name='DSI_EXP', inputs={}, **kwargs):
		super(DSI_EXP, self).__init__(
			name=name,
			interface=DSIStudioExport(**inputs),
			**kwargs)
			
