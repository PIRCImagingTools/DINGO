import os
from nipype import config, logging

from DINGO.utils import (DynImport, read_config, split_chpid, find_best,
						join_strs, add_id_subs, fileout_util)
from DINGO.wf import (HelperFlow, SplitIDs, FileIn, FileOut,
						run_fileout)
from DINGO.base import DINGO, DINGOflow, DINGOnode

from nipype import IdentityInterface, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces.base import traits, DynamicTraitedSpec, isdefined
from nipype.interfaces.utility import Merge
from nipype.interfaces import fsl
from nipype.workflows.dmri.fsl import tbss

from traits.api import Trait

#config.enable_debug_mode()
#logging.update_logging(config)
	

class HelperFSL(DINGO):
	
	def __init__(self, **kwargs):
		wfm = {
		'Neonatal_tbss_reg'		:	'DINGO.fsl',
		'Reorient'				:	'DINGO.fsl',
		'EddyC'					:	'DINGO.fsl',
		'BET'					:	'DINGO.fsl',
		'DTIFIT'				:	'DINGO.fsl',
		'FLIRT'					:	'DINGO.fsl',
		'FNIRT'					:	'DINGO.fsl',
		'ApplyWarp'				:	'DINGO.fsl'
		}
		
		super(HelperFlow, self).__init__(workflow_to_module=wfm, **kwargs)
			
	
class Reorient(DINGOnode):
	#_inputnode = 'reorient'
	#_outputnode = 'reorient'

	connection_spec = {
		'in_file'		:	['FileIn', 'dti']
	}
	
	def __init__(self, name='Reorient', inputs={}, **kwargs):
		super(Reorient, self).__init__(
			name=name, 
			interface=fsl.Reorient2Std(**inputs),
			**kwargs)
		
		#reorient = pe.Node(
			#name='reorient',
			#interface=fsl.Reorient2Std(**inputs))
		#self.add_nodes([reorient])
	

class EddyC(DINGOnode):
	#_inputnode = 'eddyc'
	#_outputnode = 'eddyc'

	connection_spec = {
		'in_file'		:	['Reorient', 'out_file']
	}
	
	def __init__(self, name='EddyC', inputs={}, **kwargs):
		super(EddyC, self).__init__(
			name=name, 
			interface=fsl.EddyCorrect(**inputs),
			**kwargs)
		#eddyc = pe.Node(
			#name='eddyc',
			#interface=fsl.EddyCorrect(**inputs))
		#self.add_nodes([eddyc])
	

class BET(DINGOnode):
	#_inputnode = 'bet'
	#_outputnode = 'bet'

	connection_spec = {
		'in_file'		:	['EddyC', 'eddy_corrected']
	}
	
	def __init__(self, name='BET', inputs={}, **kwargs):
		super(BET, self).__init__(
			name=name, 
			interface=fsl.BET(**inputs),
			**kwargs)
		#bet = pe.Node(
				#name='bet',
				#interface=fsl.BET(**inputs))
		#self.add_nodes([bet])
	

class DTIFIT(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'dti'
	
	connection_spec = {
		'sub_id'			:	['SplitIDs','sub_id'],
		'scan_id'			:	['SplitIDs','scan_id'],
		'uid'				:	['SplitIDs','uid'],
		'bval'				:	['FileIn','bval'],
		'bvec'				:	['FileIn','bvec'],
		'dwi'				:	['EddyC','eddy_corrected'],
		'mask'				:	['BET','mask_file']
	}
	
	def __init__(self, name='DTIFIT', bn_sep='_', inputs={}, **kwargs):
		super(DTIFIT, self).__init__(name=name, **kwargs)
		
		inputnode = pe.Node(name='inputnode',interface=IdentityInterface(
			fields=['sep','sub_id','scan_id','uid','dwi','mask','bval','bvec']))
			
		setattr(inputnode.inputs, 'sep', bn_sep)
		
		#Create DTIFit base_name
		dtibasename = pe.Node(
			name='dtibasename',
			interface=Function(
				#arg0=sub_id, arg1=scan_id, arg2=uid
				input_names=['sep','arg0','arg1','arg2'],
				output_names=['basename'],
				function=join_strs))

		#Create DTIFit node
		dti = pe.Node(
			name='dti',
			interface=fsl.DTIFit())
		for k,v in inputs.iteritems():
			setattr(dti.inputs, k, v)
			
		self.connect(inputnode, 'sep', dtibasename, 'sep')
		self.connect(inputnode, 'sub_id', dtibasename, 'arg0')
		self.connect(inputnode, 'scan_id', dtibasename, 'arg1')
		self.connect(inputnode, 'uid', dtibasename, 'arg2')
		self.connect(inputnode, 'dwi', dti, 'dwi')
		self.connect(inputnode, 'mask', dti, 'mask')
		self.connect(inputnode, 'bval', dti, 'bvals')
		self.connect(inputnode, 'bvec', dti, 'bvecs')
		self.connect(dtibasename,'basename',dti,'base_name')
	

class FLIRT(DINGOflow):
	_inputnode = 'flirt'
	_outputnode = 'flirt'

	connection_spec = {
		'in_file'	:	['DTIFIT','FA']
	}
	
	def __init__(self, name='FLIRT', inputs={}, **kwargs):
		super(FLIRT, self).__init__(name=name, **kwargs)
		
		flirt = pe.Node(
			name='flirt',
			interface=fsl.FLIRT(**inputs))
		self.add_nodes([flirt])
		

class FNIRT(DINGOflow):
	_inputnode = 'fnirt'
	_outputnode = 'fnirt'
	
	connection_spec = {
		'affine_file'	:	['FLIRT','out_matrix_file'],
		'in_file'		:	['DTIFIT','FA']
	}
	
	def __init__(self,name='FNIRT', inputs={}, **kwargs):
		
		
		super(FNIRT, self).__init__(name=name, **kwargs)
		
		fnirt = pe.Node(
			name='fnirt',
			interface=fsl.FNIRT(**inputs))
		self.add_nodes([fnirt])
		
class ApplyWarp(DINGOflow):
	_inputnode = 'applywarp'
	_outputnode = 'applywarp'
	
	connection_spec = {
		'in_file'		:	['FileIn','in_file'],
		'ref_file'		:	['FileIn','ref_file'],
		'field_file'	:	['FNIRT','fieldcoeff_file']
	}
	
	def __init__(self,name='fsl_applywarp', inputs={}, **kwargs):
		super(ApplyWarp, self).__init__(name=name, **kwargs)
		
		applywarp = pe.Node(
			name='applywarp',
			interface=fsl.ApplyWarp(**inputs))
		self.add_nodes([applywarp])
		
		
class FSL_genFA(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'outputnode'
	
	connection_spec = {
	
	}
		
		
class FSL_nonlinreg(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'outputnode'
	
	connection_spec = {
		'in_file'	:	['DTIFIT','FA']
	}
	
	def __init__(self, name='fsl_nonlinreg',\
	inputs=dict(\
		FA=True, flirtopts={'dof':12}, fnirtopts={'fieldcoeff_file':True}),\
	**kwargs):
		"""
		Inputs
		------
		inputnode.in_file
		inputnode.ref_file
		
		Outputs
		-------
		outputnode.affine_file
		outputnode.field_file
		"""
		
		super(FSL_nonlinreg, self).__init__(name=name, **kwargs)
		
		if 'flirtopts' in inputs:
			flirtopts = inputs['flirtopts']
		else:
			flirtopts = {}
		
		if 'fnirtopts' in inputs:
			fnirtopts = inputs['fnirtopts']
		else:
			fnirtopts = {}
			
		if 'FA' in inputs and inputs['FA']:
			if fsl.no_fsl():
				warn('NO FSL found')
			else:
				fnirtopts.update(config_file=os.path.join(os.environ["FSLDIR"],
									"etc/flirtsch/FA_2_FMRIB58_1mm.cnf"))
		
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(
				fields=['in_file','ref_file']))
				
		flirt = pe.Node(
			name='flirt',
			interface=fsl.FLIRT(**flirtopts))
			
		fnirt = pe.Node(
			name='fnirt',
			interface=fsl.FNIRT(**fnirtopts))
			
		outputnode = pe.Node(
			name='outputnode',
			interface=IdentityInterface(
				fields=['affine_file','field_file']))
					
		self.connect(inputnode, 'in_file', flirt, 'in_file')
		self.connect(inputnode, 'ref_file', flirt, 'reference')
		self.connect(inputnode, 'in_file', fnirt, 'in_file')
		self.connect(inputnode, 'ref_file', fnirt, 'ref_file')
		self.connect(flirt, 'out_matrix_file', fnirt, 'affine_file')
		self.connect(flirt, 'out_matrix_file', outputnode, 'affine_file')
		self.connect(fnirt, 'fieldcoeff_file', outputnode, 'field_file')
		
		
class TBSS_prereg(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'tbss1.outputnode'
	
	connection_spec = {
		'fa_list'	:	['DTIFIT','FA']
	}	
	
	def __init__(self, name='TBSS_prereg', reqJoin=True, **kwargs):
		super(TBSS_prereg, self).__init__(name=name, **kwargs)
		
		if reqJoin:			
			inputnode = pe.JoinNode(
				name='inputnode',
				interface=IdentityInterface(
					fields=['fa_list']),
					mandatory_inputs=True,
				joinsource=self._joinsource,
				joinfield=['fa_list'])
		else:
			inputnode = pe.Node(
				name='inputnode',
				interface=IdentityInterface(
					fields=['fa_list']),
					mandatory_inputs=True)
			
		#tbss1 workflow: erode fas, create mask, slices		
		tbss1 = tbss.create_tbss_1_preproc(name='tbss1')
		#inputnode: fa_list
		#outputnode: fa_list (not the same), mask_list, slices
		
		self.connect(inputnode, 'fa_list', tbss1, 'inputnode.fa_list')
		

class TBSS_reg_NXN(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'tbss2'
	
	connection_spec = {
		'fa_list'	:	['TBSS_prereg','fa_list'],
		'mask_list'	:	['TBSS_prereg','mask_list']
	}
	
	def __init__(self, name='TBSS_reg_NXN',\
	inputs=dict(fa_list=None, mask_list=None, id_list=None),\
	**kwargs):
		
		super(TBSS_reg_NXN, self).__init__(name=name, **kwargs)
							
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(
				fields=['fa_list','mask_list','id_list']),
				mandatory_inputs=True)
				
		if 'fa_list' in inputs and inputs['fa_list'] is not None:
			inputnode.inputs.fa_list = inputs['fa_list']
		if 'mask_list' in inputs and inputs['mask_list'] is not None:
			inputnode.inputs.mask_list = inputs['mask_list']
		if 'id_list' in inputs and inputs['id_list'] is not None:
			inputnode.inputs.id_list = inputs['id_list']
				
		#In order to iterate over something not set in advance, workflow must be
		#in a function node, within a map node with the proper iterfield
		#tbss2 workflow: registration nxn
		tbss2 = pe.MapNode(
			name='tbss2',
			interface=Function(
				input_names=[
					'target_id','target',
					'id_list','fa_list','mask_list'],
				output_names=['mat_list','fieldcoeff_list','mean_median_list'],
				function=TBSS_reg_NXN.tbss2_target),
			iterfield=['target','target_id'])
			
		self.connect([
			(inputnode, tbss2, [('id_list','target_id'),
								('fa_list','target'),
								('id_list', 'id_list'),
								('fa_list','fa_list'),
								('mask_list','mask_list')])
			])
		
						
	@staticmethod
	def create_tbss_2_reg(name="tbss_2_reg",\
	target=None, target_id=None, id_list=None, fa_list=None, mask_list=None):
		"""TBSS nonlinear registration:
		Performs flirt and fnirt from every file in fa_list to a target.
		
		Inputs
		------
		inputnode.id_list			:	List[Str]
		inputnode.fa_list			:	List[FA file]
		inputnode.mask_list			:	List[mask file]
		inputnode.target			:	FA file
		inputnode.target_id			:	Str
		
		Outputs
		-------
		outputnode.mat_list			:	List[Transform matrix]
		outputnode.fieldcoeff_list	:	List[Fieldcoeff file]
		outputnode.mean_median_list	:	List[Float, Float]
		"""
		
		tbss2 = pe.Workflow(name=name)
		
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(
				fields=['target','target_id','id_list','fa_list','mask_list']),
			mandatory_inputs=True)
			
		if target is not None:
			inputnode.inputs.target_img = target
		if target_id is not None:
			inputnode.inputs.target_id = target_id
		if id_list is not None:
			inputnode.inputs.input_id = id_list
		if fa_list is not None:
			inputnode.inputs.input_img = fa_list
		if mask_list is not None:
			inputnode.inputs.input_mask = mask_list
			
		i2r = pe.MapNode(
			name='i2r',
			interface=Function(
				#arg0=input_id, arg1=to, arg2=target_id
				input_names=['sep','arg0','arg1','arg2'],
				output_names=['i2r'],
				function=join_strs),
			iterfield=['arg0'])
			
		i2r.inputs.sep = '_'
		i2r.inputs.arg1 = 'to'
		
		i2rwarp = pe.MapNode(
			name='i2rwarp',
			interface=Function(
				#arg0=input_to_target, arg1=suffix
				input_names=['sep','arg0','arg1'],
				output_names=['i2rwarp'],
				function=join_strs),
			iterfield=['arg0'])
			
		i2rwarp.sep = '_'
		i2rwarp.arg1 = 'warp'
		
		tbss2.connect([
			(inputnode, i2r, 
				[('input_id','arg0'),
				('target_id','arg2')]),
			(i2r, i2rwarp,
				[('i2r','arg0')])
			])
				
		#Registration
		flirt = pe.MapNode(
			name='flirt',
			interface=fsl.FLIRT(dof=12),
			iterfield=['in_file','in_weight'])

		fnirt = pe.MapNode(
			name='fnirt',
			interface=fsl.FNIRT(fieldcoeff_file=True),
			iterfield=['in_file','fieldcoeff_file'])
				
		if fsl.no_fsl():
			warn('NO FSL found')
		else:
			config_file = os.path.join(os.environ['FSLDIR'],
										'etc/flirtsch/FA_2_FMRIB58_1mm.cnf')
			fnirt.inputs.config_file=config_file
				
		tbss2.connect([
			(inputnode, flirt, 
				[('input_img','in_file'),
				('target_img','reference'),
				('input_mask','in_weight')]),
			(inputnode, fnirt, 
				[('input_img','in_file'),
				('target_img','ref_file')]),
			(i2r, flirt, 
				[('i2r','out_file')]),
			(i2rwarp, fnirt,
				[('i2rwarp','fieldcoeff_file')]),
			(flirt, fnirt, 
				[('out_matrix_file', 'affine_file')])
			])

		#Estimate mean & median deformation
		sqrTmean = pe.MapNode(
			name='sqrTmean',
			interface=fsl.ImageMaths(op_string='-sqr -Tmean'),
			iterfield=['in_file'])
		
		meanmedian = pe.Node(
			name='meanmedian',
			interface=fsl.ImageStats(op_string='-M -P 50'),
			iterfield=['in_file'])

		outputnode = pe.Node(
			name='outputnode',
			interface=IdentityInterface(
				fields=['linear_matrix','fieldcoeff_file','mean_median']))

		tbss2.connect([
			(flirt, outputnode, [('out_matrix_file', 'linear_matrix')]),
			(fnirt, sqrTmean, [('fieldcoeff_file','in_file')]),
			(fnirt, outputnode, [('fieldcoeff_file', 'fieldcoeff_file')]),
			(sqrTmean, meanmedian, [('out_file','in_file')]),
			(meanmedian, outputnode, [('out_stat', 'mean_median')])
			])
			
		return tbss2
	
	@staticmethod	
	def tbss2_target(n_procs=None, \
	target=None, target_id=None, id_list=None, fa_list=None, mask_list=None):
		"""Wrap tbss2 workflow in mapnode(functionnode) to iterate over fa_files
		"""
		
		if (target is not None) and \
		(target_id is not None) and \
		(id_list is not None) and \
		(fa_list is not None) and \
		(mask_list is not None):
			tbss2n = TBSS_reg_NXN.create_tbss_2_reg_n(
				name='tbss2n',
				target=target,
				target_id=target_id,
				id_list=id_list,
				fa_list=fa_list,
				mask_list=mask_list)
			
			if (n_procs is None) or (not isinstance(n_procs, int)):
				n_procs=1
			
			tbss2n.run(plugin='MultiProc', plugin_args={'n_procs': n_procs})
			mat_list = tbss2n.result.outputs.outputnode.mat_list
			fieldcoeff_list = tbss2n.result.outputs.outputnode.fieldcoeff_list
			mean_median_list = tbss2n.result.outputs.outputnode.mean_median_list
			
			return mat_list, fieldcoeff_list, mean_median_list
		
		
		
class TBSS_postreg(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'outputnode'
	
	connection_spec = {
		'fa_list'		:	['TBSS_prereg','fa_list'],
		'field_list'	:	['TBSS_reg_NXN','fieldcoeff_list'],
		'mm_list'		:	['TBSS_reg_NXN','mean_median_list']
	}
	
	#Join is still required for best target
	#going from list[files] to list[list[files]]
	def __init__(self, name='TBSS_postreg',\
	inputs=dict(target='best',estimate_skeleton=True,suffix='warp'), **kwargs):
		
		if 'target' not in inputs:
			inputs.update(target='best')
		else:
			inputs.update(target='FMRIB58_FA_1mm.nii.gz')
		
		#super to set _joinsource
		super(TBSS_postreg, self).__init__(name=name, **kwargs)
			
		if inputs['target']=='best':
			inputnode = pe.JoinNode(
				name='inputnode',
				interface=IdentityInterface(
					fields=['id_list','fa_list','field_list','mm_list']),
				joinsource=self._joinsource,
				joinfield=['field_list','mm_list'])
		else:
			inputnode = pe.Node(
				name='inputnode',
				interface=IdentityInterface(
					fields=['id_list','fa_list','field_list','mm_list']))
		
		if 'estimate_skeleton' not in inputs:
			inputs.update(estimate_skeleton=True)
			
		if 'suffix' not in inputs:
			inputs.update(suffix='warp')
			
				
		tbss3 = TBSS_postreg.create_tbss_3_postreg(**inputs)
		
		self.connect([
			(inputnode, tbss3, [('id_list','inputnode.id_list'),
								('fa_list','inputnode.fa_list'),
								('field_list','inputnode.field_list')
								('mm_list','inputnode.mm_list')])
			])
					
	@staticmethod
	def create_find_best(name="find_best"):
		"""Find best target for FA warps, to minimize mean deformation
		
		Inputs
		------
		inputnode.id_list
		inputnode.fa_list
		inputnode.fields_lists
		inputnode.means_medians_lists
		All synced lists
		
		Outputs
		-------
		outputnode.best_id
		outputnode.best_fa
		outputnode.best_fa2MNI
		outputnode.best_fa2MNI_mat
		outputnode.2best_fields_list
		"""
		fb = pe.Workflow(name=name)
		
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(
				fields=[
					'id_list',
					'fa_list',
					'fields_lists',
					'means_medians_lists']))
					
		findbestnode = pe.Node(
			name='findbestnode',
			interface=Function(
				input_names=['id_list','list_numlists'],
				output_names=['best_index','best_id','best_mean','best_median'],
				function=find_best))
		
		selectfa = pe.Node(
			name='selectfa',
			interface=Select())
			
		selectfields = pe.Node(
			name='selectfields',
			interface=Select())
		
		fb.connect([
			(inputnode, findbestnode, 
				[('id_list','id_list'),
				('means_medians_lists','list_numlists')]),
			(inputnode, selectfa, [('fa_list','inlist')]),
			(inputnode, selectfields, [('fields_lists','inlist')]),
			(findbestnode, selectfa, [('best_index','index')]),
			(findbestnode, selectfields, [('best_index','index')])
			])
		
		#register best to MNI152
		bestmask = pe.Node(
			name='bestmask',
			interface=fsl.ImageMaths(op_string='-bin'))
			
		best2MNI = pe.Node(
			name='best2MNI',
			interface=fsl.FLIRT(dof=12))
			
		if fsl.no_fsl():
			warn('NO FSL found')
		else:
			best2MNI.inputs.reference = fsl.Info.standard_image(
				"FMRIB58_FA_1mm.nii.gz")
		
		#Group output to one node		
		outputnode = pe.Node(
			name='outputnode',
			interface=IdentityInterface(
				fields=[
					'best_id',
					'best_fa',
					'best_fa2MNI',
					'best_fa2MNI_mat',
					'2best_fields_list']))
				
		fb.connect([
			(selectfa, bestmask, [('out','in_file')]),
			(selectfa, best2MNI, [('out','in_file')]),
			(bestmask, best2MNI, [('out_file','in_weight')]),
			(best2MNI, outputnode,
				[('out_file','best_fa2MNI'),
				('out_matrix_file','best_fa2MNI_mat')]),
			(findbestnode, outputnode, [('best_id','best_id')]),
			(selectfa, outputnode, [('out','best_fa')]),
			(selectfields, outputnode, [('out','2best_fields_list')])
			])
		return fb
		
	@staticmethod
	def create_tbss_3_postreg(name='tbss_3_postreg',\
	estimate_skeleton=True, suffix=None, target='best',\
	id_list=None, fa_list=None, field_list=None, mm_list=None):
		"""find best target from fa_list, then apply warps
		
		Parameters
		----------
		name				:	Str (Workflow name)
		estimate_skeleton	:	Bool
		suffix				:	Str (default 'warp')
		target				:	'best' or 'FMRIB58_FA_1mm.nii.gz'
		id_list				:	inputnode.id_list
		fa_list				:	inputnode.fa_list
		field_list			:	inputnode.field_list
		mm_list				:	inputnode.means_medians_lists
		
		Returns
		-------
		tbss3				:	Nipype workflow
		
		Inputs
		------
		inputnode.id_list				: List[Str]
		inputnode.fa_list				: List[FA file]
		inputnode.field_list			: List[Field file] OR List[List[Field file]]
			if target='best', default, then List[List[Field file]]
		inputnode.means_medians_lists	: List[Float, Float] OR List[List[Flo,Flo]]
			if target='best', default, then List[List[Float, Float]]
		
		Outputs
		-------
		outputnode.xfmdfa_list
		outputnode.groupmask_file
		outputnode.skeleton_file
		outputnode.meanfa_file
		outputnode.mergefa_file
		"""
		
		tbss3 = pe.Workflow(name=name)
		
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(
				fields=[
					'id_list',
					'fa_list',
					'field_list',
					'means_medians_lists']))

		if id_list is not None:
			inputnode.inputs.id_list = id_list
		if fa_list is not None:
			inputnode.inputs.fa_list = fa_list
		if field_list is not None:
			inputnode.inputs.field_list = field_list
		if mm_list is not None:
			inputnode.inputs.means_medians_lists = mm_list
		
		#Apply warp to best
		applywarp = pe.MapNode(
			name='applywarp',
			interface=fsl.ApplyWarp(),
			iterfield=['in_file', 'field_file'])
			
		if fsl.no_fsl():
			warn('NO FSL found')
		else:
			applywarp.inputs.ref_file = fsl.Info.standard_image(
				"FMRIB58_FA_1mm.nii.gz")
			
		if target == 'best':
			#Find best target that limits mean deformation, insert before applywarp
			fb = TBSS_postreg.create_find_best(name='find_best')
			
			rename2target = pe.MapNode(
				name='rename2target',
				interface=Function(
					#seems to be input alphabetically, sep is only named kwarg
					#arg0=input_id, arg1=to, arg2=target_id, arg3=suffix
					input_names=['sep','arg0','arg1','arg2','arg3'],
					output_names=['string'],
					function=join_strs),
				iterfield=['arg0'])
			rename2target.inputs.sep = '_'
			rename2target.inputs.arg1 = 'to'
			if suffix is None:
				suffix = 'warp'
			rename2target.inputs.arg3 = suffix
				
			tbss3.connect([
				(inputnode, fb, 
					[('fa_list','inputnode.fa_list'),
					('field_list','inputnode.fields_lists'),
					('id_list','inputnode.id_list'),
					('means_medians_lists','inputnode.means_medians_lists')]),
				(inputnode, rename2target, 
					[('id_list','arg0')]),
				(inputnode, applywarp, 
					[('fa_list','in_file')]),
				(fb, rename2target, [('outputnode.best_id','arg2')]),
				(fb, applywarp, 
					[('outputnode.2best_fields_list','field_file'),
					('outputnode.best_fa2MNI_mat','postmat')]),
				(rename2target, applywarp, 
					[('string','out_file')])
			])
		elif target == 'FMRIB58_FA_1mm.nii.gz':
			tbss3.connect([
				(inputnode, applywarp, 
					[("fa_list", "in_file"),
					("field_list", "field_file")])
				])

			
		# Merge the FA files into a 4D file
		mergefa = pe.Node(
			name='mergefa',
			interface=fsl.Merge(dimension='t'))
			
		# Get a group mask
		groupmask = pe.Node(
			name='groupmask',
			interface=fsl.ImageMaths(
				op_string="-max 0 -Tmin -bin",
				out_data_type="char",
				suffix="_mask"))

		maskgroup = pe.Node(
			name='maskgroup',
			interface=fsl.ImageMaths(
				op_string="-mas",
				suffix="_masked"))
			
		# Create outputnode
		outputnode = pe.Node(
			name='outputnode',
			interface=IdentityInterface(
				fields=['xfmdfa_list',#may not work
					'groupmask_file',
					'skeleton_file',
					'meanfa_file',
					'mergefa_file']))
					
		#join warped files
		#JoinNode in a nested workflow is bugged in Nipype 0.10.0, neurodebian's pkg
		# for Ubuntu 14.04
		#updating to nipype 1.0.0 (with the 'fix') lead to an error for JoinNodes
		#that were in the top level workflow
		xfmfajoin = pe.JoinNode(
			name='xfmfajoin',
			interface=IdentityInterface(
				fields=['xfmdfa_list']),
			joinsource='applywarp',
			joinfield=['xfmdfa_list'])
		tbss3.connect(applywarp, 'out_file', xfmfajoin, 'xfmdfa_list')
		tbss3.connect(xfmfajoin, 'xfmdfa_list', outputnode, 'xfmdfa_list')
			
		tbss3.connect([
			(applywarp, mergefa, [("out_file", "in_files")]),
			(mergefa, groupmask, [("merged_file", "in_file")]),
			(mergefa, maskgroup, [("merged_file", "in_file")]),
			(groupmask, maskgroup, [("out_file", "in_file2")]),
			])
			
		if estimate_skeleton:
			# Take the mean over the fourth dimension
			meanfa = pe.Node(
				name='meanfa',
				interface=fsl.ImageMaths(
					op_string="-Tmean",
					suffix="_mean"))

			# Use the mean FA volume to generate a tract skeleton
			makeskeleton = pe.Node(
			name='makeskeleton',
			interface=fsl.TractSkeleton(skeleton_file=True))
				
			tbss3.connect([
				(maskgroup, meanfa, [("out_file", "in_file")]),
				(meanfa, makeskeleton, [("out_file", "in_file")]),
				(groupmask, outputnode, [('out_file', 'groupmask_file')]),
				(makeskeleton, outputnode, [('skeleton_file', 'skeleton_file')]),
				(meanfa, outputnode, [('out_file', 'meanfa_file')]),
				(maskgroup, outputnode, [('out_file', 'mergefa_file')])
				])
		else:
			#$FSLDIR/bin/fslmaths $FSLDIR/data/standard/FMRIB58_FA_1mm -mas mean_FA_mask mean_FA
			maskstd = pe.Node(
				name='maskstd',
				interface=fsl.ImageMaths(
					op_string="-mas",
					suffix="_masked"))
			maskstd.inputs.in_file = fsl.Info.standard_image("FMRIB58_FA_1mm.nii.gz")

			#$FSLDIR/bin/fslmaths mean_FA -bin mean_FA_mask
			binmaskstd = pe.Node(
				name='binmaskstd',
				interface=fsl.ImageMaths(op_string="-bin"))

			#$FSLDIR/bin/fslmaths all_FA -mas mean_FA_mask all_FA
			maskgroup2 = pe.Node(
				name='maskgroup2',
				interface=fsl.ImageMaths(
					op_string="-mas",
					suffix="_masked"))

			tbss3.connect([
				(groupmask, maskstd, [("out_file", "in_file2")]),
				(maskstd, binmaskstd, [("out_file", "in_file")]),
				(maskgroup, maskgroup2, [("out_file", "in_file")]),
				(binmaskstd, maskgroup2, [("out_file", "in_file2")])
				])

			outputnode.inputs.skeleton_file = fsl.Info.standard_image("FMRIB58_FA-skeleton_1mm.nii.gz")
			tbss3.connect([
				(binmaskstd, outputnode, [('out_file', 'groupmask_file')]),
				(maskstd, outputnode, [('out_file', 'meanfa_file')]),
				(maskgroup2, outputnode, [('out_file', 'mergefa_file')])
				])
				
		return tbss3

def create_reorient(name='fsl_reorient', **kwargs):
	reorient = pe.Node(
		name=name,
		interface=fsl.Reorient2Std())
	for k,v in kwargs.iteritems():
		setattr(reorient.inputs, k, v)
	return reorient

def create_eddyc(name='fsl_eddyc', **kwargs):
	eddyc = pe.Node(
		name=name,
		interface=fsl.EddyCorrect())
	for k,v in kwargs.iteritems():
		setattr(eddyc.inputs, k, v)
	return eddyc

def create_bet(name='fsl_bet', **kwargs):
	bet = pe.Node(
			name=name,
			interface=fsl.BET())
	for k,v in kwargs.iteritems():
		setattr(bet.inputs, k, v)
	return bet

def create_dtifit(name='fsl_dtifit', bn_sep='_', **kwargs):
	
	dtifit = pe.Workflow(name=name)
		
	#Create DTIFit base_name
	dtibasename = pe.Node(
		name='dtibasename',
		interface=Function(
			#arg0=sub_id, arg1=scan_id, arg2=uid
			input_names=['sep','arg0','arg1','arg2'],
			output_names=['basename'],
			function=join_strs))
			
	setattr(dtibasename, 'sep', bn_sep)

	#Create DTIFit node
	dti = pe.Node(
		name='dti',
		interface=fsl.DTIFit())
	for k,v in kwargs.iteritems():
		setattr(dti.inputs, k, v)
		
	dtifit.connect(dtibasename,'basename',dti,'base_name')	
	return dtifit
	
def create_flirt(name='fsl_flirt', **kwargs):
	flirt = pe.Node(
		name=name,
		interface=fsl.FLIRT())
	for k,v in kwargs.iteritems():
		setattr(fnirt.inputs, k, v)
	return flirt

def create_fnirt(name='fsl_fnirt', **kwargs):
	fnirt = pe.Node(
		name=name,
		interface=fsl.FNIRT())
	for k,v in kwargs.iteritems():
		setattr(fnirt.inputs, k, v)
	return fnirt
	
def create_applywarp(name='fsl_applywarp', **kwargs):
	applywarp = pe.Node(
		name=name,
		interface=fsl.ApplyWarp())
	for k,v in kwargs.iteritems():
		setattr(applywarp.inputs, k, v)
	return applywarp
	

def create_genFA(name="genFA", \
grabFiles=False, doreorient='create_reorient', doeddy='create_eddyc',\
dobet='create_bet', dodti='create_dtifit',\
parent_dir=None, sub_id=None, scan_id=None, uid=None):
	"""
	Inputs
	------
	inputnode.parent_dir
	inputnode.sub_id
	inputnode.scan_id
	inputnode.uid
	inputnode.dwi
	inputnode.bval
	inputnode.bvec
	
	Default Outputs
	-------
	outputnode.eddyc_file
	outputnode.mask_file
	outputnode.FA_file
	outputnode.V1_file
	"""
	from DINGO.main import Info
	
	genFA = pe.Workflow(name=name)
	
	###Pre-Processing###
	inputnode = pe.Node(
		name="inputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir","sub_id","scan_id","uid",
				"dwi","bval","bvec","mask"]))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
	if sub_id is not None:
		inputnode.inputs.sub_id = sub_id
	if scan_id is not None:
		inputnode.inputs.scan_id = scan_id
	if uid is not None:
		inputnode.inputs.uid = uid
		

	grabfields = []
	grabexts = []
	#Create reorient node
	_, reorient_func = 	DynImport(mod=DINGO.wf_to_mod(doreorient), 
								  obj=doreorient)
	if reorient_func is not None:
		reorient = reorient_func(name='reorient')
		
	#Create eddy correct node
	_, eddy_func = DynImport(mod=DINGO.wf_to_mod(doeddy),
							obj=doeddy)
	if eddy_func is not None:
		eddy = eddy_func(name='eddy', ref_num=0)
		
	#Create brain extraction node
	_, bet_func = DynImport(mod=DINGO.wf_to_mod(dobet),
							obj=dobet)
	if bet_func is not None:
		bet = bet_func(name='bet', robust=True, mask=True)
	else:
		grabfields.append('mask')#TODO adjust for runtime
		grabexts.append('_mask.nii.gz')#TODO adjust for runtime
		
	#Create and connect dtifit subflow
	_, dti_func = DynImport(mod=DINGO.wf_to_mod(dodti),
							obj=dodti)
	if dti_func is not None:
		dti = dti_func(name='dti')
		grabfields.extend(('dwi','bval','bvec'))#TODO adjust for runtime
		grabexts.extend(('.nii.gz','.bval','.bvec'))#TODO adjust for runtime
		
	
	#Create and connect datagrabber node
	if grabFiles:
		datain = FileIn(name='datain',
			infields=['sub_id','scan_id','uid'], 
			exts=grabexts, outfields=grabfields)
		genFA.connect([ (inputnode, datain, 
			[('parent_dir','base_directory'),
			('sub_id','sub_id'),
			('scan_id','scan_id'),
			('uid','uid')] ) ])
	
	#Connect reorient node
	if reorient_func is not None:
		if grabFiles:
			genFA.connect(datain, 'dwi', reorient, 'in_file')
		else:
			genFA.connect(inputnode, 'dwi', reorient, 'in_file')
			
	#Connect eddy correct node
	if eddy_func is not None:
		if reorient_func is not None:
			genFA.connect(reorient, 'out_file', eddy, 'in_file')
		else:
			genFA.connect(inputnode,'dwi', eddy, 'in_file')
			
	#Connect brain extraction node
	if bet_func is not None:
		if eddy_func is not None:
			genFA.connect(eddy, 'eddy_corrected', bet, 'in_file')
		elif reorient_func is not None:
			genFA.connect(reorient, 'out_file', bet, 'in_file')
		else:
			genFA.connect(inputnode, 'dwi', bet, 'in_file')
			
	#Connect dtifit subflow
	if dti_func is not None:
		#connect dwi
		if eddy_func is not None:
			genFA.connect(eddy, 'eddy_corrected', dti, 'dti.dwi')
		elif reorient_func is not None:
			genFA.connect(reorient, 'out_file', dti, 'dti.dwi')
		elif grabFiles:
			genFA.connect(datain, 'dwi', dti, 'dti.dwi')
		else:
			genFA.connect(inputnode, 'dwi', dti, 'dti.dwi')
		#connect bval, bvec
		if grabFiles:
			genFA.connect([ (datain, dti, [
				('bval','dti.bvals'),
				('bvec','dti.bvecs')] ) ])
		else:
			genFA.connect([ (inputnode, dti, [
				('bval','dti.bvals'),
				('bvec','dti.bvecs')] ) ])
		#connect mask
		if bet_func is not None:
			genFA.connect(bet, 'mask_file', dti, 'dti.mask')
		else:
			genFA.connect(inputnode, 'mask', dti, 'dti.mask')
		#connect basename
		genFA.connect([ (inputnode, dti, [
			('sub_id','dtibasename.arg0'),
			('scan_id','dtibasename.arg1'),
			('uid','dtibasename.arg2')] ) ])
			
	if eddy_func is not None and \
	bet_func is not None and \
	dti_func is not None:
		outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"eddyc_file",
				"mask_file",
				"FA_file",
				"V1_file"]))
		genFA.connect([
			(eddy, outputnode, [('eddy_corrected','eddyc_file')]),
			(bet, outputnode, [('mask_file','mask_file')]),
			(dti, outputnode, 
				[("dti.FA", "FA_file"),
				('dti.V1','V1_file')] ) ])
	
	return genFA


def create_invwarp_all2best(name="invwarp_all2best",fadir=None, outdir=None):
	"""Calculate inverse warps of files, FAs in one dir, INVwarp in one dir"""
	
	invwarpwf = pe.Workflow(name=name)
	
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'data_dir',
				'best_id',
				'all_ids'],
			mandatory_inputs=True))
	inputnode.iterables=('all_ids',inputnode.inputs.all_ids)
	if fadir is not None:
		inputnode.inputs.data_dir = fadir
			
	#grab warps from disk
	datainnode = pe.Node(
		name='datainnode',
		interface=nio.DataGrabber(
			infields=[
				'best_id',
				'other_id'],
			outfields=[
				'other2best',
				'other']))
	#datainnode.inputs.base_directory = inputnode.inputs.data_dir
	datainnode.inputs.template = '%s_to_%s_warp.nii.gz'
	datainnode.inputs.sort_filelist = True
	datainnode.inputs.field_template = dict(
		other2best='%s_to_%s_warp.nii.gz',
		other='%s.nii.gz')
	datainnode.inputs.template_args = dict(
		other2best=[['other_id','best_id']],
		other=[['other_id']])
		
	renamenode = pe.Node(
		name='rename',
		interface=Rename(
			format_string='%(best_id)s_to_%(other_id)s.nii.gz'))
			
	invwarpnode = pe.Node(
		name='invwarp',
		interface=fsl.utils.InvWarp())
	invwarpnode.inputs.relative = True #may not need to be set
		
	dataoutnode = pe.Node(
		name='dataoutnode',
		interface=nio.DataSink())
	dataoutnode.inputs.substitutions = [('.nii.gz', '_FINVwarp.nii.gz')]
	if outdir is not None:
		dataoutnode.inputs.base_directory=outdir
	
	outputnode = pe.Node(
		name='outputnode',
		interface=IdentityInterface(
			fields=['invwarp_file'],
			mandatory_inputs=True))
		
	
	invwarpwf.connect([
		(inputnode, datainnode, 
			[('data_dir','base_directory'),
			('best_id','best_id'),
			('all_ids','other_id')]),
		(datainnode, renamenode, 
			[('best_id','best_id'),
			('other_id','other_id')]),
		(datainnode, invwarpnode, 
			[('other2best','warp'),
			('other','reference')]),
		(renamenode, invwarpnode, 
			[('out_file','inverse_warp')]),
		(invwarpnode, dataoutnode, 
			[('inverse_warp','container.scan.@invwarp')]),
		(invwarpnode, outputnode, 
			[('inverse_warp','invwarp_file')])
		])
		
	return invwarpwf
	
	
def id_from_filename(in_file):
	import os
	fixed = in_file
	for i in range(in_file.count('.')):
		fixed,_ = os.path.splitext(os.path.basename(fixed))
	return fixed
	

def create_ind_nonlinreg(name='ind_nonlinreg',\
parent_dir=None, sinkFiles2in=False, sinkFiles2ref=False, splitid4sink=False,\
id_sep='_', in_id=None, ref_id=None,\
in_file=None, in_mask=None,\
ref_file=None, ref_mask=None,\
flirtopts=None, fnirtopts=None):
	indnonlinreg = pe.Workflow(name)
		
	#Input
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=['parent_dir','in_file','in_mask','in_id','id_sep',
					'ref_file','ref_mask','ref_id']))
					
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
		indnonlinreg.base_dir = parent_dir
	else:
		indnonlinreg.base_dir = os.getcwd()
			
	if in_file is not None:
		inputnode.inputs.in_file = in_file
		if in_id is not None:
			inputnode.inputs.in_id = in_id
		else:
			inputnode.inputs.in_id = id_from_filename(in_file)
		
	if ref_file is not None:
		inputnode.inputs.ref_file = ref_file
		if ref_id is not None:
			inputnode.inputs.ref_id = ref_id
		else:
			inputnode.inputs.ref_id = id_from_filename(ref_file)
		
	if in_mask is not None:
		inputnode.inputs.in_mask = in_mask
	if ref_mask is not None:
		inputnode.inputs.ref_mask = ref_mask
		
	if id_sep is not None:
		inputnode.inputs.id_sep = id_sep
		
	#Filename strings - implement the defaults from respective interfaces
	#but allows for input to be absolute paths to files
	
	i2r = pe.Node(
		name='i2r',
		interface=Function(
			#arg0=input_id, arg1=to, arg2=reference_id
			input_names=['sep','arg0','arg1','arg2'],
			output_names=['string'],
			function=join_strs))
	i2r.inputs.sep = '_'
	i2r.inputs.arg1 = 'to'
	
	i2rniigz = pe.Node(
		name='i2rniigz',
		interface=Function(
			input_names=['sep','arg0','arg1'],
			output_names=['nifti'],
			function=join_strs))
	i2rniigz.inputs.sep=''
	i2rniigz.inputs.arg1='.nii.gz'
			
	
	i2rflirt = pe.Node(
		name='i2rflirt',
		interface=Function(
			#arg0=input_to_reference, arg1=suffix
			input_names=['sep','arg0','arg1'],
			output_names=['flirt'],
			function=join_strs))
	i2rflirt.inputs.sep = '_'
	i2rflirt.inputs.arg1 = 'flirt.mat'
	
	i2rfieldwarp = pe.Node(
		name='i2rfieldwarp',
		interface=Function(
			#arg0=input_to_reference, arg1=suffix
			input_names=['sep','arg0','arg1'],
			output_names=['fieldwarp'],
			function=join_strs))
	i2rfieldwarp.inputs.sep = '_'
	i2rfieldwarp.inputs.arg1 = 'fieldwarp.nii.gz'
	
	i2rwarped = pe.Node(
		name='i2rwarped',
		interface=Function(
			#arg0=input_to_reference, arg1=suffix
			input_names=['sep','arg0','arg1'],
			output_names=['warped'],
			function=join_strs))
	i2rwarped.inputs.sep = '_'
	i2rwarped.inputs.arg1 = 'warped.nii.gz'
	
	indnonlinreg.connect([
		(inputnode, i2r, 
			[('in_id','arg0'),
			('ref_id','arg2')]),
		(i2r, i2rniigz,
			[('string','arg0')]),
		(i2r, i2rflirt,
			[('string','arg0')]),
		(i2r, i2rfieldwarp,
			[('string','arg0')]),
		(i2r, i2rwarped,
			[('string','arg0')]) ])
	
	#Registration
	if flirtopts is None:
		flirtopts = dict()
	if fnirtopts is None:
		fnirtopts = dict()
	
	flirtopts.update(dof=12)
	fnirtopts.update(fieldcoeff_file=True)
	flirt = create_flirt(name='flirt', **flirtopts)
	fnirt = create_fnirt(name='fnirt', **fnirtopts)	
	
	indnonlinreg.connect(
		inputnode, 'in_file', 
		flirt, 'in_file')
	indnonlinreg.connect(
		inputnode, 'ref_file', 
		flirt, 'reference')
	indnonlinreg.connect(
		inputnode, 'in_mask', 
		flirt, 'in_weight')
	indnonlinreg.connect(
		inputnode, 'ref_mask', 
		flirt, 'ref_weight')
	
	indnonlinreg.connect(
		inputnode, 'in_file', 
		fnirt, 'in_file')
	indnonlinreg.connect(
		inputnode, 'ref_file', 
		fnirt, 'ref_file')
		
	indnonlinreg.connect(
		i2rniigz, 'nifti', 
		flirt, 'out_file')
	indnonlinreg.connect(
		i2rflirt,'flirt',
		flirt,'out_matrix_file')
	indnonlinreg.connect(
		i2rfieldwarp, 'fieldwarp', 
		fnirt, 'fieldcoeff_file')
	indnonlinreg.connect(
		i2rwarped, 'warped', 
		fnirt, 'warped_file')		
	indnonlinreg.connect(
		flirt, 'out_matrix_file', 
		fnirt, 'affine_file')
		
	#Output
	outputnode = pe.Node(
		name='outputnode',
		interface=IdentityInterface(
			fields=['matrix_file','fieldcoeff_file','warped_file']))
			
	indnonlinreg.connect(
		flirt,'out_matrix_file',
		outputnode,'matrix_file')
	indnonlinreg.connect(
		fnirt,'fieldcoeff_file',
		outputnode,'fieldcoeff_file')
	indnonlinreg.connect(
		fnirt,'warped_file',
		outputnode,'warped_file')
		
		
	#SinkFiles
	if sinkFiles2in:
		id4sink = 'in_id'
	elif sinkFiles2ref:
		id4sink = 'ref_id'
		
	dataout = pe.Node(name='dataout',interface=nio.DataSink())
		
	if splitid4sink:
		splitids = create_split_ids(name='splitids')
		#get parameterized container
		dataout.inputs.parameterization = False #handled by setting container
		indnonlinreg.connect(inputnode,id4sink,splitids,'inputnode.scan_list')
		
		util = pe.Node(
		name='util',
		interface=Function(
			input_names=['names','file_list','substitutions',
				'sub_id','scan_id','uid'],
			output_names=['container','out_file_list','newsubs'],
			function=fileout_util))
			
		#set the normal way, scan_list_sep was ending up undefined
		indnonlinreg.connect(
			inputnode,'id_sep',
			splitids,'inputnode.scan_list_sep')
		indnonlinreg.connect(
			splitids,'outputnode.sub_id',
			util,'sub_id')
		indnonlinreg.connect(
			splitids,'outputnode.scan_id',
			util,'scan_id')
		indnonlinreg.connect(
			splitids,'outputnode.uid',
			util,'uid')
		indnonlinreg.connect(
			util,'container',
			dataout,'container')
				
	elif sinkFiles2in or sinkFiles2ref:
		#container is id,parameterization True (default)
		indnonlinreg.connect(
			inputnode,id4sink,
			dataout,'container')

		
	indnonlinreg.connect(
		inputnode,'parent_dir',
		dataout,'base_directory')
	indnonlinreg.connect(
		flirt,'out_matrix_file',
		dataout,'reg.@matrix')
	indnonlinreg.connect(
		fnirt,'fieldcoeff_file',
		dataout,'reg.@fieldcoeff')
	indnonlinreg.connect(
		fnirt,'warped_file',
		dataout,'reg.@warped')
	
	return indnonlinreg
	
	
def testpath(inpath, inpotparent):
	if os.path.exists(inpath):
		return inpath
	else:
		test = os.path.join(inpotparent,inpath)
		if os.path.exists(test):
			return test
		else:
			raise IOError('Path: %s does not exist with or without Parent: %s' %
				(inpath, inpotparent))
	

def create_nonlinreg(name='nonlinreg', doreg='fsl_fnirt',
parent_dir=None, other_dir=None,\
img_list=None, mask_list=None, other_img=None, other_mask=None,\
id_list=None, other_id=None, id_sep='_',\
derive_mask_from_id=False, derive_omask_from_id=False,\
subscancont_idlist=False, subscancont_otherid=False,\
flirtopts=None, fnirtopts=None,\
warp2other=True, FA=False,\
sinkFiles2=None, splitid4sink=False):
	
	nonlinreg = pe.Workflow(name=name)
	
	#Input
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=['parent_dir','img_list','mask_list','id_list', 'id_sep',
				'other_dir','other_img','other_mask','other_id']))
	
	if parent_dir is None:
		parent_dir = os.getcwd()
	nonlinreg.base_dir = parent_dir
	inputnode.inputs.parent_dir = parent_dir
	
	if other_dir is None:
		other_dir = parent_dir
	inputnode.inputs.other_dir = other_dir
	
	#List
	iterablelist = []
	iinfields = []
	ioutfields = ['imgfile']
	ifield_template = dict()
	itemplate_args = dict()
	
	if derive_mask_from_id:
		iinfields.append('mask_sfx')
		ioutfields.append('maskfile')
		
	if id_list is not None:
		if not isinstance(id_list, (list,tuple)):
			id_list = [id_list]
		iterablelist.append(('id_list',id_list))
		
		#placeholder to duplicate finding ids from img_list - connect to reg
		get_list_ids = pe.Node(name='get_list_ids',interface=IdentityInterface(
			fields=['fixed']))
			
		if subscancont_idlist:
			#files stored in parent_dir/sub_id/scan_id/subid_scanid_uid
			splitlist = create_split_ids(name='splitlist',scan_list_sep=id_sep)
			
			#update grabber fields
			iinfields.extend(('sub_id','scan_id','uid'))
			ifield_template.update(imgfile='%s/%s/%s_%s_%s.nii.gz')
			itemplate_args.update(imgfile=
				[['sub_id','scan_id','sub_id','scan_id','uid']])
				
			if derive_mask_from_id:
				ifield_template.update(maskfile='%s/%s/%s_%s_%s_%s.nii.gz')
				itemplate_args.update(maskfile=
					[['sub_id','scan_id','sub_id','scan_id','uid','mask_sfx']])
				
			#grabber - instantiate before connect
			in_files = pe.Node(name='in_files',interface=nio.DataGrabber(
				infields=iinfields, outfields=ioutfields, sort_filelist=True))
			
			#connect
			nonlinreg.connect(
				inputnode,'id_list',splitlist,'inputnode.scan_list')
			nonlinreg.connect(
				inputnode,'id_sep',splitlist,'inputnode.scan_list_sep')
			nonlinreg.connect(
				splitlist,'outputnode.sub_id',in_files,'sub_id')
			nonlinreg.connect(
				splitlist,'outputnode.scan_id',in_files,'scan_id')
			nonlinreg.connect(
				splitlist,'outputnode.uid',in_files,'uid')
			nonlinreg.connect(inputnode,'mask_list',in_files,'mask_sfx')
		else:
			#files stored in parent_dir
			iinfields.append('inid')
			ifield_template.update(imgfile='%s.nii.gz')
			itemplate_args.update(imgfile=[['inid']])
			
			if derive_mask_from_id:
				ifield_template.update(maskfile='%s_%s.nii.gz')
				itemplate_args.update(maskfile=[['inid','mask_sfx']])
				
			in_files = pe.Node(name='in_files',interface=nio.DataGrabber(
				infields=iinfields, outfields=ioutfields, sort_filelist=True))
			
			nonlinreg.connect(inputnode,'id_list',in_files,'inid')
			nonlinreg.connect(inputnode,'mask_list',in_files,'mask_sfx')
			
		nonlinreg.connect(inputnode,'parent_dir',in_files,'base_directory')
	elif img_list is not None:
		if not isinstance(img_list, (list,tuple)):
			img_list = [img_list]
		iterablelist.append(('img_list',img_list))
		
		iinfields.append('imgpath')
		ifield_template.update(imgfile='%s')
		itemplate_args.update(imgfile=[['imgpath']])
		
		if mask_list is not None:
			if not isinstance(mask_list, (list,tuple)):
				mask_list = [mask_list]
					
			if len(img_list) != len(mask_list):
				raise AttributeError('Number of elements in img_list and '
					'mask_list must match')
					
			iterablelist.append(('mask_list',mask_list))
			iinfields.append('maskpath')
			ifieldtemplate.update(maskfile=[['%s']])
			itemplate_args.update(maskfile=[['maskpath']])
		
		in_files = pe.Node(name='in_files',interface=nio.DataGrabber(
			infields=iinfields,outfields=ioutfields,sort_filelist=True))
			
		get_list_ids = pe.Node(name='get_list_ids',interface=Function(
			input_names=['in_file'],
			output_names=['fixed'],
			function=id_from_filename))
			
		nonlinreg.connect(inputnode,'img_list',get_list_ids,'in_file')
		nonlinreg.connect(inputnode,'parent_dir',in_files,'base_directory')
		nonlinreg.connect(inputnode,'img_list',in_files,'imgpath')
		nonlinreg.connect(inputnode,'mask_list',in_files,'maskpath')
		
	in_files.inputs.field_template = ifield_template
	in_files.inputs.template_args = itemplate_args
	in_files.inputs.template='%s'
		
	if len(iterablelist) > 0:
		inputnode.iterables = iterablelist
		inputnode.synchronize = True
		
	#Other Image
	oinfields = []
	ooutfields = ['otherimg']
	ofield_template = dict()
	otemplate_args = dict()
	
	#irrespective of grab style
	if derive_omask_from_id:
		oinfields.append('mask_sfx')
		ooutfields.append('othermask')
	
	if other_id is not None:
		inputnode.inputs.other_id = other_id
		
		get_other_id = pe.Node(name='get_other_id',interface=IdentityInterface(
			fields=['fixed']))
			
		if subscancont_otherid:
			#otherid stored in other_dir/sub_id/scan_id/subid_scanid_uid
			splitotherid = create_split_ids(name='splitotherid',
				scan_list_sep=id_sep)
			#img fields
			oinfields.extend(('sub_id','scan_id','uid'))
			ofield_template.update(
				otherimg='%s/%s/%s_%s_%s.nii.gz')
			otemplate_args.update(
				otherimg=[['sub_id','scan_id','sub_id','scan_id','uid']])
			#mask fields
			if derive_omask_from_id:
				ofield_template.update(otherimg=
					'%s/%s/%s_%s_%s_%s.nii.gz')
				otemplate_args.update(otherimg=
					[['sub_id','scan_id','sub_id','scan_id','uid','mask_sfx']])
			#datagrabber node
			otherin = pe.Node(name='otherin',interface=nio.DataGrabber(
				infields=oinfields, outfields=ooutfields))
			
			nonlinreg.connect(
				inputnode,'other_id',splitotherid,'inputnode.scan_list')
			nonlinreg.connect(
				inputnode,'id_sep',splitotherid,'inputnode.scan_list_sep')
			nonlinreg.connect(inputnode,'other_mask',otherin,'mask_sfx')
			nonlinreg.connect(
				splitotherid,'outputnode.sub_id',otherin,'sub_id')
			nonlinreg.connect(
				splitotherid,'outputnode.scan_id',otherin,'scan_id')
			nonlinreg.connect(
				splitotherid,'outputnode.uid',otherin,'uid')
		else:
			#img fields
			oinfields.append('otherid')
			ofield_template.update(otherimg='%s.nii.gz')
			otemplate_args.update(otherimg=[['otherid']])
			#mask fields
			if derive_omask_from_id:
				ofield_template.update(othermask='%s_%s.nii.gz')
				otemplate_args.update(othermask=[['otherid','mask_sfx']])
			#datagrabber node
			otherin = pe.Node(name='otherin',interface=nio.DataGrabber(
				infields=oinfields, outfields=ooutfields))
			otherin.inputs.template = '%s'
			nonlinreg.connect(inputnode,'other_id',otherin,'otherid')
			nonlinreg.connect(inputnode,'other_mask',otherin,'mask_sfx')
		
	#specify particular file because it does not have sub_scan_uid format
	elif other_img is not None:
		oinfields.append('otherinpath')
		ofield_template.update(otherimg='%s')
		otemplate_args.update(otherimg=[['otherinpath']])
		inputnode.inputs.other_img = other_img
			
		if other_mask is not None:
			oinfields.append('othermaskpath')
			ofield_template.update(othermask='%s')
			otemplate_args.update(othermask=[['othermaskpath']])
			inputnode.inputs.other_mask = other_mask
			
		otherin = pe.Node(name='otherin',interface=nio.DataGrabber(
			infields=oinfields, outfields=ooutfields))
			
		get_other_id = pe.Node(name='get_other_id',interface=Function(
			input_names=['in_file'],
			output_names=['fixed'],
			function=id_from_filename))
			
		nonlinreg.connect(inputnode,'other_img',get_other_id,'in_file')
		nonlinreg.connect(inputnode,'other_img',otherin,'otherinpath')
		nonlinreg.connect(inputnode,'other_mask',otherin,'othermaskpath')
		
	#Finally, apply field templates, args, dir
	nonlinreg.connect(inputnode,'other_dir',otherin,'base_directory')
	otherin.inputs.field_template = ofield_template
	otherin.inputs.template_args = otemplate_args
	otherin.inputs.template = '*'
	otherin.inputs.sort_filelist = True
	
	
	#Registration
	if flirtopts is None:
		flirtopts = dict(dof=12)
	if fnirtopts is None:
		fnirtopts = dict(fieldcoeff_file=True)
	
	if FA:
		if fsl.no_fsl():
			warn('NO FSL found')
		else:
			fnirtopts.update(
				config_file=os.path.join(os.environ['FSLDIR'],
									'etc/flirtsch/FA_2_FMRIB58_1mm.cnf'))
		
	create_ind_params = {
		'fsl_fnirt': {
			'parent_dir':parent_dir,
			'flirtopts':flirtopts,
			'fnirtopts':fnirtopts,
			'splitid4sink':splitid4sink} }
	
	if sinkFiles2 is None:
		pass
	elif sinkFiles2 == 'id_list':
		if warp2other:
			create_ind_params[doreg].update(sinkFiles2in=True)
		else:
			create_ind_params[doreg].update(sinkFiles2ref=True)
	elif sinkFiles2 == 'other_id':
		if warp2other:
			create_ind_params[doreg].update(sinkFiles2ref=True)
		else:
			create_ind_params[doreg].update(sinkFiles2in=True)
		
	reg = create_ind_nonlinreg(**create_ind_params[doreg])
	
	if warp2other:#warp list to other
		indmap = {
		'inputnode.in_file'	:	(in_files,'imgfile'),
		'inputnode.in_mask'	:	(in_files,'maskfile'),
		'inputnode.in_id'		:	(get_list_ids,'fixed'),
		'inputnode.ref_file'	:	(otherin,'otherimg'),
		'inputnode.ref_mask'	:	(otherin,'othermask'),
		'inputnode.ref_id'	:	(get_other_id,'fixed')}
	else:#warp other to list
		indmap = {
		'inputnode.ref_file'	:	(in_files,'imgfile'),
		'inputnode.ref_mask'	:	(in_files,'maskfile'),
		'inputnode.ref_id'	:	(get_list_ids,'fixed'),
		'inputnode.in_file'	:	(otherin,'otherimg'),
		'inputnode.in_mask'	:	(otherin,'othermask'),
		'inputnode.in_id'		:	(get_other_id,'fixed')}
		
	for k,v in indmap.iteritems():
		if v[1] in v[0].outputs.__dict__:
			nonlinreg.connect(v[0],v[1],reg,k)
		
	#Join Output
	outputnode = pe.JoinNode(
		name='outputnode',
		interface=IdentityInterface(
			fields=['matrix_list','fieldcoeff_list','warped_list']),
		joinsource='inputnode',
		joinfield=['matrix_list','fieldcoeff_list','warped_list'])
		
	nonlinreg.connect(
		reg,'outputnode.matrix_file',
		outputnode,'matrix_list')
	nonlinreg.connect(
		reg,'outputnode.fieldcoeff_file',
		outputnode,'fieldcoeff_list')
	nonlinreg.connect(
		reg,'outputnode.warped_file',
		outputnode,'warped_list')
		
	return nonlinreg
	
	
def create_warp_regions(name='warp_regions',\
region_list=None, field_file=None, ref_file=None, warpopts=None):
	warp = pe.Workflow(name=name)
	
	inputnode = pe.Node(name='inputnode', interface=IdentityInterface(
		fields=['region_list','field_file', 'ref_file']))
		
	outputnode = pe.JoinNode(name='outputnode', interface=IdentityInterface(
		fields=['warped_region_list']),
		joinsource='inputnode',
		joinfield=['warped_region_list'])
	
	if region_list is not None:
		inputnode.inputs.region_list = region_list
		
	if field_file is not None:
		inputnode.inputs.field_file = field_file
		
	if ref_file is not None:
		inputnode.inputs.ref_file = ref_file
		
	if warpopts is None:
		warpopts = dict(relwarp=True)
		
	inputnode.iterables = [('region_list', inputnode.inputs.region_list)]
	
	applywarp = pe.Node(name='applywarp', interface=fsl.ApplyWarp(**warpopts))
	
	warp.connect(inputnode,'region_list',
				applywarp,'in_file')
	warp.connect(inputnode,'field_file',
				applywarp,'field_file')
	warp.connect(inputnode,'ref_file',
				applywarp,'ref_file')
	warp.connect(applywarp,'out_file',
				outputnode,'warped_region_list')
	
	return warp
	

def create_tbss_registration(name='tbss_reg',\
genFA=True, tbss1=True, tbss2_best=True, tbss3_best=True,\
parent_dir=None, scan_list=None, scan_list_sep='_'):
	"""Register FA files to best representative, merge and average
	
	Parameters
	------
	name		:	Str (workflow name)
	parent_dir	:	Directory (parent directory of subject folders)
	scan_list	:	List[Str] 
		(Scan ID, e.g. ['0761_MR1_42D_DTI','CHD_052_01a_DTIFIXED'])
		
	Returns
	-------
	tbss_reg	:	Nipype workflow
	
	reg = create_tbss_reg(name='tbss_reg',
	parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
	scan_list=['0761_MR1_42D_DTI','CHD_052_01a_DTIFIXED'])
	"""
	reg = pe.Workflow(name=name)
	
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'parent_dir',
				'scan_list',
				'scan_list_sep'],
			mandatory_inputs=True))
	
	#check inputs
	if parent_dir is None:
		msg='create_registration:parent_dir must be specified'
		raise NameError(msg)
		
	if (scan_list is None) or (not isinstance(scan_list, (list,tuple))):
		msg='create_registration:scan_list must be specified list or tuple'
		raise NameError(msg)
		
	if (scan_list_sep is None) or (not isinstance(scan_list_sep, (str))):
		msg='create_registration:scan_list_sep must be specified str'
		raise NameError(msg)
	
	#update reg.base_dir and inputnode fields since checks passed
	reg.base_dir = parent_dir
	inputnode.inputs.parent_dir = parent_dir
	inputnode.inputs.scan_list = scan_list
	inputnode.iterables = ('scan_list', inputnode.inputs.scan_list)
	inputnode.inputs.scan_list_sep = scan_list_sep
		
	#split scan_list 
	split = create_split_ids(name='split',scan_list_sep='_')
	#inputnode: scan_list, scan_list_sep
	#outputnode: sub_id, scan_id, uid
	
	#get basic container directory	sub_id/scan_id
	cn = pe.Node(
		name='cn',
		interface=Function(
			#arg0=sub_id, arg1=scan_id
			input_names=['sep','arg0','arg1'],
			output_names=['subscan'],
			function=join_strs))
	cn.inputs.sep='/'
	
	#connect id utilities
	reg.connect([
		(inputnode, split,
			[('scan_list','inputnode.scan_list'),
			('scan_list_sep','inputnode.scan_list_sep')]),
		(split, cn,
			[('outputnode.sub_id','arg0'),
			('outputnode.scan_id','arg1')])
	])
	
	if genFA:
		#create FA file creation workflow
		fa = create_genFA(name='fa',grabFiles=True)
		#inputnode: parent_dir, sub_id, scan_id, uid
		#outputnode: eddyc_file, mask_file, FA_file, V1_file
		
		#create output of fa from nipype cache to subject/scan/prep folders
		faout = pe.Node(
			name='faout',
			interface=nio.DataSink(infields=[
				'prep.@eddyc','prep.@fa','prep.@v1','prep.@mask']))
		faout.inputs.substitutions = [('reoriented','ro'),('edc','ec')]
		faout.inputs.parameterization = False #handled by cn -> datasink connection
			
		#connect fa creation workflows
		reg.connect([
			(inputnode, fa, [('parent_dir','inputnode.parent_dir')]),
			(inputnode, faout, [('parent_dir','base_directory')]),
			(split, fa, 
				[('outputnode.sub_id','inputnode.sub_id'),
				('outputnode.scan_id','inputnode.scan_id'),
				('outputnode.uid','inputnode.uid')]),
			(cn, faout, [('subscan','container')]),
			(fa, faout, 
				[('outputnode.eddyc_file','prep.@eddyc'),
				('outputnode.mask_file','prep.@mask'),
				('outputnode.FA_file','prep.@fa'),
				('outputnode.V1_file','prep.@v1')])
		])
	
	if tbss1:
		#put FA_files in list, container in list = len(tbss1out.inputs.items()) same
		#regular JoinNode isn't working
		#error in nipype.pipeline.engine.utils.generate_expanded_graph
		fajoin = pe.JoinNode(
			name='fajoin',
			interface=IdentityInterface(
				fields=['fa_']),
			joinsource='inputnode',
			joinfield=['fa_'])
			
		containerjoin = pe.JoinNode(
			name='containerjoin',
			interface=IdentityInterface(
				fields=['container_']),
			joinsource='inputnode',
			joinfield=['container_'])
			
		#tbss1 workflow: erode fas, create mask, slices		
		tbss1 = tbss.create_tbss_1_preproc(name='tbss1')
		#inputnode: fa_list
		#outputnode: fa_list (not the same), mask_list, slices
		
		#create output of tbss1 from nipype cache to subject/scan/tbss1 folders
		tbss1out = pe.MapNode(
			name='tbss1out',
			interface=nio.DataSink(
				infields=[
				'tbss1.@fa','tbss1.@mask','tbss1.@slice']),
			iterfield=['container','tbss1.@fa','tbss1.@mask','tbss1.@slices'])
		tbss1out.inputs.parameterization = False #handled by cn -> datasink connect
		
		#connect fajoin, tbss1, tbss1out
		reg.connect([
			(inputnode, tbss1out,
				[('parent_dir','base_directory')]),
			(fa, fajoin, 
				[('outputnode.FA_file','fa_')]),
			(cn, containerjoin,
				[('subscan','container_')]),
			(fajoin, tbss1,
				[('fa_','inputnode.fa_list')]),
			(containerjoin, tbss1out,
				[('container_','container')]),
			(tbss1, tbss1out, 
				[('outputnode.fa_list','tbss1.@fa'),
				('outputnode.mask_list','tbss1.@mask'),
				('outputnode.slices','tbss1.@slices')])
		])
	
	if tbss2_best:
		#In nipype in order to iterate over something not set in advance, workflow
		#must be in a function node, within a map node with the proper iterfield
		#tbss2 workflow: registration nxn in this case
		tbss2 = pe.MapNode(
			name='tbss2_best',
			interface=Function(
				input_names=[
					'target_id','target',
					'id_list','fa_list','mask_list'],
				output_names=['mat_list','fieldcoeff_list','mean_median_list'],
				function=tbss2_target),
			iterfield=['target','target_id'])
		tbss2.inputs.id_list = scan_list
		tbss2.inputs.target_id = scan_list#iterated
		
		#create output of tbss2 from nipype cache to subject/scan/tbss2 folders
		#tranforms TO a subject/scan will end up there
		tbss2out = pe.MapNode(
			name='tbss2out',
			interface=nio.DataSink(
				infields=[
					'tbss2.@mat_file',
					'tbss2.@fieldcoeff_file',
					'tbss2.@mean_median_file']),
			iterfield=[
				'container',
				'tbss2.@matfile',
				'tbss2.@fieldcoeff_file',
				'tbss2.@mean_median_file'])
		#tbss2out.inputs.parameterization = False #off for debug purposes
					
		#connect tbss2 (id_list,target_id already input), tbss2out
		reg.connect([
			(inputnode, tbss2out, [('parent_dir', 'base_directory')]),
			(fajoin, tbss2out, [('container_list','container')]),#iterated
			(tbss2, tbss2out,
				[('mat_list','tbss2.@mat_file'),#iterated
				('fieldcoeff_list','tbss2.@fieldcoeff_file'),#iterated
				('mean_median_list','tbss2.@mean_median_file')])#iterated
		])
		
		if tbss1:
			reg.connect([
				(tbss1, tbss2,
					[('outputnode.fa_list','target'),#iterated
					('outputnode.fa_list','fa_list'),
					('outputnode.mask_list','mask_list')])
			])
		else:
			print('Connect: tbss2.target, tbss2.fa_list, tbss2.mask_list before'
				' running')
	
	if tbss3_best:
		#tbss 3 workflow: apply transformations, merge, mean, mask, skeletonize
		tbss3 = create_tbss_3_postreg_find_best(name='tbss3',target='best')
		#inputnode: id_list, fa_list, field_list, means_medians_lists
		#outputnode: groupmask_file, skeleton_file, mergafa_file, meanfa_file
		
		#output group averages
		tbss3gout = pe.Node(
			name='tbss3gout',
			interface=nio.DataSink(
				infields=[
					'@groupmask',
					'@skeleton',
					'@mergefa',
					'@meanfa']))
		tbss3gout.inputs.container = 'tbss3'
				
		#connect tbss3, tbss3out
		if tbss2:
			reg.connect([
				(tbss2, tbss3, [('fieldcoeff_list', 'inputnode.field_list')]),
				(tbss3, tbss3gout, 
					[('outputnode.groupmask_file','@groupmask'),
					('outputnode.skeleton_file','@skeleton'),
					('outputnode.mergefa_file','@mergefa'),
					('outputnode.meanfa_file','@meanfa')])
			])
			
			if tbss1:
				reg.connect(
					tbss1, 'outputnode.fa_list',
					tbss3, 'inputnode.fa_list')
			else:
				print('Connect: tbss3.inputnode.fa_list before running')
		else:
			print('Connect: tbss3.inputnode.field_list before running')
				
		#output xfmed subject fas
		tbss3xfmdout = pe.MapNode(
			name='tbss3xfmdout',
			interface=nio.DataSink(
				infields=['tbss3.@xfmdfa_file']),
			iterfield=['container','tbss3.@xfmdfa_file'])
			
		#connect tbss3xfmdout
		reg.connect([
			(tbss3, tbss3xfmdout, 
				[('outputnode.xfmdfa_list', 'tbss3.@xfmdfa_file')]),
			(fajoin, tbss3xfmdout, [('container_list','container')])
		])

	return reg
