from nipype import (IdentityInterface, Function)
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces.utility import Merge
from nipype.interfaces import fsl
import os
import logging
from DINGO.utils import (update_dict, read_config)
from DINGO.DSI_Studio_base import (DSIStudioSource, DSIStudioReconstruct, 
								DSIStudioTrack, DSIStudioAnalysis)
from DINGO.base import (DINGO, DINGOflow, DINGOnode)


class HelperDSI(DINGO):
	def __init__(self, **kwargs):
		wfm = {
			'DSI_SRC'	:	'DINGO.DSI_Studio',
			'REC_prep'	:	'DINGO.DSI_Studio',
			'DSI_REC'	:	'DINGO.DSI_Studio',
			'DSI_TRK'	:	'DINGO.DSI_Studio',
		}
		super(HelperDSI, self).__init__(workflow_to_module=wfm, **kwargs)

class DSI_SRC(DINGOnode):
	"""Nipype node to create a src file in DSIStudio with dwi, bval, bvec
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'DSI_SRC')
	inputs		:	Dict (Node InputName=ParameterValue)
	**kwargs	:	Workflow InputName=ParameterValue
	
	e.g. dsi_src = DSI_SRC(name='dsi_src',\
							inputs={'output':'mydtifile.nii.gz',\
									'bval':'mybvalfile.bval',\
									'bvec':'mybvecfile.bvec'})
					
	Returns
	-------
	Nipype workflow
		dsi_src.outputs.output = mydtifile.src.gz
	"""
	
	connection_spec = {
		'source'		:	['EddyC','eddy_corrected'],
		'bval'			:	['FileIn','bval'],
		'bvec'			:	['FileIn','bvec']
	}
	
	def __init__(self, name="DSI_SRC", inputs={}, **kwargs):
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
	inputs={'op_string':'-ero', 'suffix':'_ero'}, **kwargs):
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
	
	e.g. dsi_rec = DSI_REC(name='dsi_rec',
							inputs={'source':mysrcfile.src.gz,\
									'mask':mymaskfile.nii.gz,\
									'method':'dti'})
					
	Returns
	-------
	Nipype workflow
		dsi_rec.outputs.fiber_file=mysrcfile.src.gz.dti.fib.gz
	"""
	
	connection_spec = {
		'source'		:	['DSI_SRC','output'],
		'mask'			:	['REC_prep','out_file']
	}

	def __init__(self, name="DSI_REC", inputs={}, **kwargs):
		super(DSI_REC, self).__init__(
			name=name,
			interface=DSIStudioReconstruct(**inputs),
			**kwargs)
			
		
		
class DSI_TRK(DINGOflow):
	"""Nipype wf to create a trk with fiber file and input parameters
	DSIStudioTrack.inputs will not seem to reflect the config until
	self._check_mandatory_inputs(), part of run() and cmdline(), is executed
	But, it the data will be in the indict field.
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'DSI_TRK')
	inputs		:	Dict Track Node InputName=ParameterValue
		(Inputs['tracts'] is used specially as an iterable, other params
		will apply to each tract)
	**kwargs	:	Workflow InputName=ParameterValue
		any unspecified tracting parameters will be defaults of DSIStudioTrack
	
	e.g. dsi_trk = DSI_TRK(name='dsi_trk',\
						inputs={'source':'myfibfile.fib.gz',\
								'rois':['myROI1.nii.gz','myROI2.nii.gz'],\
								'roas':['myROA.nii.gz'],\
								'tract_name':'track'})
					
	Returns
	-------
	Nipype workflow
		dsi_trk.outputnode.outputs=['tract_list']
		e.g. os.path.abspath(myfibfile_track.nii.gz)
	"""
	_inputnode = 'inputnode'
	_outputnode = 'outputnode'
	
	connection_spec = {
		'fib_file'		:	['DSI_REC','fiber_file']
	}
	def __init__(self, name="DSI_TRK", inputs={}, **kwargs):
		
		import copy
		super(DSI_TRK, self).__init__(name=name, **kwargs)
		
		#Parse inputs
		inputnode = pe.Node(name='inputnode',
			interface=IdentityInterface(
				fields=[
					'fib_file',
					'tractnames_list', 
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
			universalinputs = copy.deepcopy(inputs)
			del universalinputs['tracts']
			for tract in inputs['tracts'].iterkeys():
				for k,v in universalinputs.iteritems():
					if k not in inputs['tracts'][tract]:
						inputs['tracts'][tract].update(k=v)

			inputnode.iterables = [
				('tractnames_list', inputs['tracts'].keys()),
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
		
		#DSI Studio will only accept 5 ROIs or 5 ROAs. A warning would normally 
		#be shown that only the first five listed will be used, but merging the 
		#ROAs is viable.
		merge_roas = DSI_TRK.create_merge_roas(name='merge_roas')

		trknode = pe.Node(
			name="trknode",
			interface=DSIStudioTrack())
			
		###TODO regex match regions to file grab of niftis in subject region_dir
			
		self.connect([
			(inputnode, trknode, [('fib_file','source'),
								('tractnames_list','tract_name')]),
			(inputnode, merge_roas, [('tract_inputs','inputnode.tract_input')]),
			(merge_roas, trknode, [('outputnode.new_tract_input','indict'),
								('outputnode.new_roa','roas')]),
			(trknode, outputnode, [('tract','tract_list')])
			])
					
	def create_merge_roas(name='merge_roas'):
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
			
		separate_roas = pe.Node(
			name='separate_roas',
			interface=Function(
				input_names=['tract_input'],
				output_names=['new_tract_input', 'roa_list'],
				function=separate_roas))
		
		mergenode = pe.Node(
			name='mergenode',
			interface=fsl.Merge(dimension='t'))
			
		maxnode = pe.Node(
			name='maxnode',
			interface=fsl.ImageMaths(op_string='-Tmax'))
			
		outputnode = pe.Node(
			name='outputnode',
			interface=IdentityInterface(
				fields=['new_tract_input', 'new_roa']))
				
		merge.connect([
			(inputnode, separate_roas, [('tract_input', 'tract_input')]),
			(separate_roas, mergenode, [('roa_list', 'in_files')]),
			(separate_roas, outputnode,[('new_tract_input','new_tract_input')]),
			(mergenode, maxnode, [('merged_file', 'in_file')]),
			(maxnode, outputnode, [('out_file', 'new_roa')])
			])
		
		return merge
		

