import os
from warnings import warn
from DINGO.base import DINGO, DINGOFlow, DINGONode
from DINGO.utils import (join_strs)

from nipype import (IdentityInterface, Function, config)
from nipype.interfaces.utility import Select
from nipype.interfaces import fsl
import nipype.pipeline.engine as pe
from nipype.workflows.dmri.fsl import tbss

# DINGONode boilerplate now unnecessary, may reference interface in setup config directly
# Left for the moment to ease transition


class HelperFSL(DINGO):
    
    def __init__(self, **kwargs):
        wfm = {
            'Reorient':     'DINGO.workflows.fsl',
            'EddyC':        'DINGO.workflows.fsl',
            'BET':          'DINGO.workflows.fsl',
            'DTIFIT':       'DINGO.workflows.fsl',
            'FLIRT':        'DINGO.workflows.fsl',
            'ApplyXFM':     'DINGO.workflows.fsl',
            'FNIRT':        'DINGO.workflows.fsl',
            'ApplyWarp':    'DINGO.workflows.fsl',
            'FSLNonLinReg': 'DINGO.workflows.fsl',
            'TBSSPreReg':   'DINGO.workflows.fsl',
            'TBSSRegNXN':   'DINGO.workflows.fsl',
            'TBSSPostReg':  'DINGO.workflows.fsl',
        }
        
        super(HelperFSL, self).__init__(workflow_to_module=wfm, **kwargs)
            
    
class Reorient(DINGONode):

    connection_spec = {
        'in_file':   ['FileIn', 'dti']
    }
    
    def __init__(self, name='Reorient', inputs={}, **kwargs):
        super(Reorient, self).__init__(
            name=name, 
            interface=fsl.Reorient2Std(**inputs),
            **kwargs)
    

class EddyC(DINGONode):

    connection_spec = {
        'in_file':   ['Reorient', 'out_file']
    }
    
    def __init__(self, name='EddyC', inputs={}, **kwargs):
        super(EddyC, self).__init__(
            name=name, 
            interface=fsl.EddyCorrect(**inputs),
            **kwargs)
    

class BET(DINGONode):

    connection_spec = {
        'in_file':   ['EddyC', 'eddy_corrected']
    }
    
    def __init__(self, name='BET', inputs={}, **kwargs):
        super(BET, self).__init__(
            name=name, 
            interface=fsl.BET(**inputs),
            **kwargs)
    

class DTIFIT(DINGOFlow):
    inputnode = 'inputnode'
    outputnode = 'dti'
    
    connection_spec = {
        'sub_id':   ['SplitIDs', 'sub_id'],
        'scan_id':   ['SplitIDs', 'scan_id'],
        'uid':   ['SplitIDs', 'uid'],
        'bval':   ['FileIn', 'bval'],
        'bvec':   ['FileIn', 'bvec'],
        'dwi':   ['EddyC', 'eddy_corrected'],
        'mask':   ['BET', 'mask_file']
    }
    
    def __init__(self, name='DTIFIT', bn_sep='_', inputs={}, **kwargs):
        super(DTIFIT, self).__init__(name=name, **kwargs)
        
        inputnode = pe.Node(name='inputnode', interface=IdentityInterface(
            fields=['sep', 'sub_id', 'scan_id', 'uid', 'dwi', 'mask', 'bval', 'bvec']))
            
        setattr(inputnode.inputs, 'sep', bn_sep)
        
        # Create DTIFit base_name
        dtibasename = pe.Node(
            name='dtibasename',
            interface=Function(
                # arg0=sub_id, arg1=scan_id, arg2=uid
                input_names=['sep', 'arg0', 'arg1', 'arg2'],
                output_names=['basename'],
                function=join_strs))

        # Create DTIFit node
        dti = pe.Node(
            name='dti',
            interface=fsl.DTIFit())
        for k, v in inputs.iteritems():
            setattr(dti.inputs, k, v)
            
        self.connect(inputnode, 'sep', dtibasename, 'sep')
        self.connect(inputnode, 'sub_id', dtibasename, 'arg0')
        self.connect(inputnode, 'scan_id', dtibasename, 'arg1')
        self.connect(inputnode, 'uid', dtibasename, 'arg2')
        self.connect(inputnode, 'dwi', dti, 'dwi')
        self.connect(inputnode, 'mask', dti, 'mask')
        self.connect(inputnode, 'bval', dti, 'bvals')
        self.connect(inputnode, 'bvec', dti, 'bvecs')
        self.connect(dtibasename, 'basename', dti, 'base_name')
    

class FLIRT(DINGONode):

    connection_spec = {
        'in_file':  ['DTIFIT', 'FA']
    }
    
    def __init__(self, name='FLIRT', inputs={}, **kwargs):
        super(FLIRT, self).__init__(
            name=name,
            interface=fsl.FLIRT(**inputs),
            **kwargs)
        

class ApplyXFM(DINGOFlow):
    
    inputnode = 'xfmnode'
    outputnode = 'xfmnode'
    connection_spec = {
        'in_matrix_file':   ['FLIRT', 'out_matrix_file']
    }
    
    def __init__(self, name='ApplyXFM', inputs={}, **kwargs):
        super(ApplyXFM, self).__init__(name=name, **kwargs)
        
        if 'iterfield' in inputs:
            iterfield = inputs['iterfield']
            del inputs['iterfield']
        else:
            iterfield = 'in_file'
        
        xfmnode = pe.MapNode(
            name='xfmnode',
            interface=fsl.ApplyXFM(**inputs),
            iterfield=iterfield)
        self.add_nodes([xfmnode])


class FNIRT(DINGONode):
    
    connection_spec = {
        'affine_file':  ['FLIRT', 'out_matrix_file'],
        'in_file':      ['DTIFIT', 'FA']
    }
    
    def __init__(self, name='FNIRT', inputs={}, **kwargs):
        super(FNIRT, self).__init__(
            name=name,
            interface=fsl.FNIRT(**inputs),
            **kwargs)
        
        
class ApplyWarp(DINGOFlow):
    
    inputnode = 'warpnode'
    outputnode = 'warpnode'
    connection_spec = {
        'in_file':      ['FileIn', 'in_file'],
        'ref_file':     ['FileIn', 'ref_file'],
        'field_file':   ['FNIRT', 'fieldcoeff_file']
    }
    
    def __init__(self, name='fsl_applywarp', inputs={}, **kwargs):
        super(ApplyWarp, self).__init__(name=name, **kwargs)
            
        if 'iterfield' in inputs:
            iterfield = inputs['iterfield']
            del inputs['iterfield']
        else:
            iterfield = 'in_file'
            
        warpnode = pe.MapNode(
            name='warpnode',
            interface=fsl.ApplyWarp(**inputs),
            iterfield=iterfield)
        self.add_nodes([warpnode])
        
        
class FSLNonLinReg(DINGOFlow):
    inputnode = 'inputnode'
    outputnode = 'outputnode'
    
    connection_spec = {
        'in_file':  ['DTIFIT', 'FA']
    }
    
    def __init__(self,
                 name='fsl_nonlinreg',
                 inputs=dict(
                     FA=True,
                     flirtopts={'dof': 12},
                     fnirtopts={'fieldcoeff_file': True}),
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
        
        super(FSLNonLinReg, self).__init__(name=name, **kwargs)
        
        if 'flirtopts' in inputs:
            flirtopts = inputs['flirtopts']
        else:
            flirtopts = {'fieldcoeff_file': True}
        
        if 'fnirtopts' in inputs:
            fnirtopts = inputs['fnirtopts']
        else:
            fnirtopts = {'dof': 12}
            
        if 'FA' in inputs and inputs['FA']:
            if fsl.no_fsl():
                warn('NO FSL found')
            else:
                fnirtopts.update(config_file=os.path.join(
                    os.environ["FSLDIR"], "etc/flirtsch/FA_2_FMRIB58_1mm.cnf"))
        
        inputnode = pe.Node(
            name='inputnode',
            interface=IdentityInterface(
                fields=['in_file', 'ref_file']))
                
        flirt = pe.Node(
            name='flirt',
            interface=fsl.FLIRT(**flirtopts))
            
        fnirt = pe.Node(
            name='fnirt',
            interface=fsl.FNIRT(**fnirtopts))
            
        outputnode = pe.Node(
            name='outputnode',
            interface=IdentityInterface(
                fields=['affine_file', 'field_file']))
                    
        self.connect(inputnode, 'in_file', flirt, 'in_file')
        self.connect(inputnode, 'ref_file', flirt, 'reference')
        self.connect(inputnode, 'in_file', fnirt, 'in_file')
        self.connect(inputnode, 'ref_file', fnirt, 'ref_file')
        self.connect(flirt, 'out_matrix_file', fnirt, 'affine_file')
        self.connect(flirt, 'out_matrix_file', outputnode, 'affine_file')
        self.connect(fnirt, 'fieldcoeff_file', outputnode, 'field_file')
        
        
class TBSSPreReg(DINGOFlow):
    inputnode = 'inputnode'
    outputnode = 'tbss1.outputnode'
    
    connection_spec = {
        'fa_list':  ['DTIFIT', 'FA']
    }    
    
    def __init__(self, name='TBSS_prereg', req_join=True, **kwargs):
        super(TBSSPreReg, self).__init__(name=name, **kwargs)
        
        if req_join:
            inputnode = pe.JoinNode(
                name='inputnode',
                interface=IdentityInterface(
                    fields=['fa_list']),
                mandatory_inputs=True,
                joinsource=self.config_inputs,
                joinfield=['fa_list'])
        else:
            inputnode = pe.Node(
                name='inputnode',
                interface=IdentityInterface(
                    fields=['fa_list']),
                mandatory_inputs=True)
            
        # tbss1 workflow: erode fas, create mask, slices
        tbss1 = tbss.create_tbss_1_preproc(name='tbss1')
        # inputnode: fa_list
        # outputnode: fa_list (not the same), mask_list, slices
        
        self.connect(inputnode, 'fa_list', tbss1, 'inputnode.fa_list')
        

class TBSSRegNXN(DINGOFlow):
    inputnode = 'inputnode'
    outputnode = 'tbss2'
    
    connection_spec = {
        'fa_list':      ['TBSS_prereg', 'fa_list'],
        'mask_list':    ['TBSS_prereg', 'mask_list']
    }
    
    def __init__(self, name='TBSS_reg_NXN',
    inputs=dict(fa_list=None, mask_list=None, id_list=None, 
                n_procs=None, memory_gb=None),
    **kwargs):
        
        super(TBSSRegNXN, self).__init__(name=name, **kwargs)
                            
        inputnode = pe.Node(
            name='inputnode',
            interface=IdentityInterface(
                fields=['fa_list', 'mask_list', 'id_list']),
            mandatory_inputs=True)
                
        if 'fa_list' in inputs and inputs['fa_list'] is not None:
            inputnode.inputs.fa_list = inputs['fa_list']
        if 'mask_list' in inputs and inputs['mask_list'] is not None:
            inputnode.inputs.mask_list = inputs['mask_list']
        if 'id_list' in inputs and inputs['id_list'] is not None:
            inputnode.inputs.id_list = inputs['id_list']
        if 'n_procs' in inputs and inputs['n_procs'] is not None:
            n_procs = inputs['n_procs']
        else:
            n_procs = 1
        if 'memory_gb' in inputs and inputs['memory_gb'] is not None:
            memory_gb = inputs['memory_gb']
        else:
            memory_gb = 2
        
        # update cfg to keep unnecessary outputs, or most of the function nodes
        # will be empty and rerun each execution
        cfg = dict(execution={'remove_unnecessary_outputs': u'false'})
        config.update_config(cfg)
        # In order to iterate over something not set in advance, workflow must be
        # in a function node, within a map node with the proper iterfield
        # tbss2 workflow: registration nxn
        tbss2 = pe.MapNode(
            name='tbss2',
            interface=Function(
                input_names=[
                    'n_procs', 'memory_gb',
                    'target_id', 'target',
                    'id_list', 'fa_list', 'mask_list'],
                output_names=['mat_list', 'fieldcoeff_list', 'mean_median_list'],
                function=TBSSRegNXN.tbss2_target),
            iterfield=['target', 'target_id'])
        tbss2.inputs.n_procs = n_procs
        tbss2.inputs.memory_gb = memory_gb
            
        self.connect([
            (inputnode, tbss2, [('id_list', 'target_id'),
                                ('fa_list', 'target'),
                                ('id_list', 'id_list'),
                                ('fa_list', 'fa_list'),
                                ('mask_list', 'mask_list')])
            ])
        
    @staticmethod
    def create_tbss_2_reg(name="tbss_2_reg",
                          target=None, target_id=None,
                          id_list=None, fa_list=None, mask_list=None):
        """TBSS nonlinear registration:
        Performs flirt and fnirt from every file in fa_list to a target.
        
        Inputs
        ------
        inputnode.id_list           :   List[Str]
        inputnode.fa_list           :   List[FA file]
        inputnode.mask_list         :   List[mask file]
        inputnode.target            :   FA file
        inputnode.target_id         :   Str
        
        Outputs
        -------
        outputnode.mat_list         :   List[Transform matrix]
        outputnode.fieldcoeff_list  :   List[Fieldcoeff file]
        outputnode.mean_median_list :   List[Float, Float]
        """
        
        tbss2 = pe.Workflow(name=name)
        
        inputnode = pe.Node(
            name='inputnode',
            interface=IdentityInterface(
                fields=['target', 'target_id', 'id_list', 'fa_list', 'mask_list']),
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
            
        # Could possibly replace i2r nodes with function in connect statements
        i2r = pe.MapNode(
            name='i2r',
            interface=Function(
                # arg0=input_id, arg1=to, arg2=target_id
                input_names=['sep', 'arg0', 'arg1', 'arg2'],
                output_names=['i2r'],
                function=join_strs),
            iterfield=['arg0'])
        i2r.inputs.sep = '_'
        i2r.inputs.arg1 = 'to'
        
        i2rwarp = pe.MapNode(
            name='i2rwarp',
            interface=Function(
                # arg0=input_to_target, arg1=suffix
                input_names=['sep', 'arg0', 'arg1'],
                output_names=['i2rwarp'],
                function=join_strs),
            iterfield=['arg0'])
        i2rwarp.inputs.sep = '_'
        i2rwarp.inputs.arg1 = 'warp.nii.gz'
        
        i2rwarped = pe.MapNode(
            name='i2rwarped',
            interface=Function(
                input_names=['sep', 'arg0', 'arg1'],
                output_names=['i2rwarped'],
                function=join_strs),
            iterfield=['arg0'])
        i2rwarped.inputs.sep = '_'
        i2rwarped.inputs.arg1 = 'warped.nii.gz'
        
        i2rnii = pe.MapNode(
            name='i2rnii',
            interface=Function(
                input_names=['sep', 'arg0', 'arg1'],
                output_names=['i2rnii'],
                function=join_strs),
            iterfield=['arg0'])
        i2rnii.inputs.sep = ''
        i2rnii.inputs.arg1 = '.nii.gz'
        
        tbss2.connect([
            (inputnode, i2r, 
                [('input_id', 'arg0'),
                 ('target_id', 'arg2')]),
            (i2r, i2rwarp,
                [('i2r', 'arg0')]),
            (i2r, i2rwarped,
                [('i2r', 'arg0')]),
            (i2r, i2rnii,
                [('i2r', 'arg0')])
            ])
                
        # Registration
        flirt = pe.MapNode(
            name='flirt',
            interface=fsl.FLIRT(dof=12),
            iterfield=['in_file', 'in_weight', 'out_file'])

        fnirt = pe.MapNode(
            name='fnirt',
            interface=fsl.FNIRT(fieldcoeff_file=True),
            iterfield=['in_file', 'affine_file', 'fieldcoeff_file', 'warped_file'])
                
        if fsl.no_fsl():
            warn('NO FSL found')
        else:
            config_file = os.path.join(
                os.environ['FSLDIR'], 'etc/flirtsch/FA_2_FMRIB58_1mm.cnf')
            fnirt.inputs.config_file = config_file
                
        tbss2.connect([
            (inputnode, flirt, 
                [('input_img', 'in_file'),
                 ('target_img', 'reference'),
                 ('input_mask', 'in_weight')]),
            (inputnode, fnirt, 
                [('input_img', 'in_file'),
                 ('target_img', 'ref_file')]),
            (i2rnii, flirt, 
                [('i2rnii', 'out_file')]),
            (i2rwarp, fnirt,
                [('i2rwarp', 'fieldcoeff_file')]),
            (i2rwarped, fnirt,
                [('i2rwarped', 'warped_file')]),
            (flirt, fnirt, 
                [('out_matrix_file', 'affine_file')])
            ])

        # Estimate mean & median deformation
        sqrtmean = pe.MapNode(
            name='sqrTmean',
            interface=fsl.ImageMaths(op_string='-sqr -Tmean'),
            iterfield=['in_file'])
        
        meanmedian = pe.MapNode(
            name='meanmedian',
            interface=fsl.ImageStats(op_string='-M -P 50'),
            iterfield=['in_file'])

        outputnode = pe.Node(
            name='outputnode',
            interface=IdentityInterface(
                fields=['linear_matrix', 'fieldcoeff', 'mean_median']))

        tbss2.connect([
            (flirt, outputnode, [('out_matrix_file', 'linear_matrix')]),
            (fnirt, sqrtmean, [('fieldcoeff_file', 'in_file')]),
            (fnirt, outputnode, [('fieldcoeff_file', 'fieldcoeff')]),
            (sqrtmean, meanmedian, [('out_file', 'in_file')]),
            (meanmedian, outputnode, [('out_stat', 'mean_median')])
            ])
            
        return tbss2

    def tbss2_target(n_procs=None, memory_gb=None,
                     target=None, target_id=None,
                     id_list=None, fa_list=None, mask_list=None):
        """Wrap tbss2 workflow in mapnode(functionnode) to iterate over fa_files
        """
        from DINGO.workflows.fsl import TBSSRegNXN
        import os
        import gzip
        import pickle
        
        if ((target is not None) and
           (target_id is not None) and
           (id_list is not None) and
           (fa_list is not None) and
           (mask_list is not None)):
            tbss2n = TBSSRegNXN.create_tbss_2_reg(
                name='tbss2n',
                target=target,
                target_id=target_id,
                id_list=id_list,
                fa_list=fa_list,
                mask_list=mask_list)
            tbss2n.base_dir = os.getcwd()
            
            if (n_procs is None) or (not isinstance(n_procs, int)):
                n_procs = 1
            if (memory_gb is None) or (not isinstance(memory_gb, int)):
                memory_gb = 2
            
            # workflow.run() returns a graph whose nodes have no output
            # but it has the directory where the result_nodename.pklz is located
            # inputnode and outputnode won't be there, get data directly
            graph = tbss2n.run(
                plugin='MultiProc', 
                plugin_args={'n_procs': n_procs,
                             'memory_gb': memory_gb})
            node_list = list(graph)
            
            node_data = {
                'flirt':        'out_matrix_file',
                'fnirt':        'fieldcoeff_file',
                'meanmedian':   'out_stat'
            }
            
            def read_result(name, data_dict, node):
                result_filename = os.path.join(
                    node.output_dir(),
                    ''.join(('result_', name, '.pklz'))
                )
                with gzip.open(result_filename, 'rb') as f:
                    data = pickle.load(f)
                return getattr(data.outputs, data_dict[name])
                
            for node in node_list:
                if node.name == 'flirt':
                    mat_list = read_result('flirt', node_data, node)
                elif node.name == 'fnirt':
                    fieldcoeff_list = read_result('fnirt', node_data, node)
                elif node.name == 'meanmedian':
                    mm_list = read_result('meanmedian', node_data, node)
            
            return mat_list, fieldcoeff_list, mm_list
        
        
class TBSSPostReg(DINGOFlow):
    inputnode = 'inputnode'
    outputnode = 'outputnode'
    
    connection_spec = {
        'fa_list':      ['TBSS_prereg', 'fa_list'],
        'field_list':   ['TBSS_reg_NXN', 'fieldcoeff_list'],
        'mm_list':      ['TBSS_reg_NXN', 'mean_median_list']
    }
    
    def __init__(self,
                 name='TBSS_postreg',
                 inputs=dict(target='best',
                             mask_best=True,
                             estimate_skeleton=True,
                             suffix='warp'),
                 **kwargs):
        
        if 'target' not in inputs:
            inputs.update(target='best')
            # other possibility is 'FMRIB58_FA_1mm.nii.gz'
        if 'estimate_skeleton' not in inputs:
            inputs.update(estimate_skeleton=True)
        if 'suffix' not in inputs:
            inputs.update(suffix='inMNI_warp.nii.gz')
        
        super(TBSSPostReg, self).__init__(name=name, **kwargs)
            
        inputnode = pe.Node(
            name='inputnode',
            interface=IdentityInterface(
                fields=['id_list', 'fa_list', 'field_list', 'mm_list']))
        if 'id_list' in inputs and inputs['id_list'] is not None:
            inputnode.inputs.id_list = inputs['id_list']
        if 'fa_list' in inputs and inputs['fa_list'] is not None:
            inputnode.inputs.fa_list = inputs['fa_list']
        if 'field_list' in inputs and inputs['field_list'] is not None:
            inputnode.inputs.field_list = inputs['field_list']
        if 'mm_list' in inputs and inputs['mm_list'] is not None:
            inputnode.inputs.fa_list = inputs['mm_list']

        tbss3 = self.create_tbss_3_postreg(**inputs)
        
        self.connect(inputnode, 'id_list', tbss3, 'inputnode.id_list')
        self.connect(inputnode, 'fa_list', tbss3, 'inputnode.fa_list')
        self.connect(inputnode, 'field_list', tbss3, 'inputnode.field_list')
        self.connect(inputnode, 'mm_list', 
                     tbss3, 'inputnode.means_medians_lists')
                    
    def find_best(id_list, list_numlists):
        """take synced id_list and list of lists with means, medians, return id and
        mean_median that are smallest"""
        nids = len(id_list)
        nnumlists = len(list_numlists)
        if nids != nnumlists:
            msg = ('N_ids: {:d} != N_lists: {:d}. Verify data and workflow'
                   .format(nids, nnumlists))
            raise IndexError(msg)
        else:
            idmeans = []
            idmedians = []
            for o in range(0, nids):
                nnums = len(list_numlists[o])
                if nids != nnums:
                    msg = ('Warning: N_nums: {:d} for ID: {} is not N_ids: {:d}'
                           .format(nnums, id_list[o], nids))
                    print(msg)
                meangen = (list_numlists[o][i][0] for i in range(0, nids))
                idmeans.append(sum(meangen) / nids)
                mediangen = (list_numlists[o][i][1] for i in range(0, nids))
                idmedians.append(sum(mediangen) / nids)
                
            best_index = idmeans.index(min(idmeans))
            best_id = id_list[best_index]
            best_mean = idmeans[best_index]
            best_median = idmedians[best_index]

        return best_index, best_id, best_mean, best_median
    
    def create_find_best(self, name="find_best", mask=True):
        """Find best target for FA warps, to minimize mean deformation

        Parameters
        ----------
        name    :   Str (workflow name, default "find_best")
        mask    :   Bool (default True) whether to binarize the best brain and
                         use to weight the transform to MNI space.

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
                input_names=['id_list', 'list_numlists'],
                output_names=['best_index', 'best_id', 'best_mean', 'best_median'],
                function=TBSSPostReg.find_best))
        
        selectfa = pe.Node(
            name='selectfa',
            interface=Select())
            
        selectfields = pe.Node(
            name='selectfields',
            interface=Select())
        
        fb.connect([
            (inputnode, findbestnode, 
                [('id_list', 'id_list'),
                 ('means_medians_lists', 'list_numlists')]),
            (inputnode, selectfa, [('fa_list', 'inlist')]),
            (inputnode, selectfields, [('fields_lists', 'inlist')]),
            (findbestnode, selectfa, [('best_index', 'index')]),
            (findbestnode, selectfields, [('best_index', 'index')])
            ])
        
        # register best to MNI152
        best2mni = pe.Node(
            name='best2MNI',
            interface=fsl.FLIRT(dof=12))
        # Sometimes poor results for flirt when using the -inweight flag,
        # Perhaps particularly for low resolution images?
        # If mask is true (default), will use it
        # Add mask = False to inputs to do the registration without
        if mask:
            bestmask = pe.Node(
                name='bestmask',
                interface=fsl.ImageMaths(op_string='-bin'))
            fb.connect([
                (selectfa, bestmask, [('out', 'in_file')]),
                (bestmask, best2mni, [('out_file', 'in_weight')])
            ])
            
        if fsl.no_fsl():
            warn('NO FSL found')
        else:
            best2mni.inputs.reference = fsl.Info.standard_image(
                "FMRIB58_FA_1mm.nii.gz")
        
        # Group output to one node
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
            (selectfa, best2mni, [('out', 'in_file')]),
            (best2mni, outputnode,
                [('out_file', 'best_fa2MNI'),
                 ('out_matrix_file', 'best_fa2MNI_mat')]),
            (findbestnode, outputnode, [('best_id', 'best_id')]),
            (selectfa, outputnode, [('out', 'best_fa')]),
            (selectfields, outputnode, [('out', '2best_fields_list')])
            ])
        return fb

    def create_tbss_3_postreg(self,
                              name='tbss_3_postreg',
                              estimate_skeleton=True,
                              suffix=None,
                              target='best',
                              mask_best=True,
                              id_list=None,
                              fa_list=None,
                              field_list=None,
                              mm_list=None):
        """find best target from fa_list, then apply warps
        
        Parameters
        ----------
        name                :   Str (Workflow name)
        estimate_skeleton   :   Bool (default True)
        suffix              :   Str (default 'warp')
        target              :   'best' or 'FMRIB58_FA_1mm.nii.gz'
        mask_best           :   Bool (default True) whether to binarize best
                                     brain and use to weight xfm to MNI space
        id_list             :   inputnode.id_list
        fa_list             :   inputnode.fa_list
        field_list          :   inputnode.field_list
        mm_list             :   inputnode.means_medians_lists
        
        Returns
        -------
        tbss3               :   Nipype workflow
        
        Inputs
        ------
        inputnode.id_list               :   List[Str]
        inputnode.fa_list               :   List[FA file]
        inputnode.field_list            :   List[Field file] OR List[List[Field file]]
            if target='best', default, then List[List[Field file]]
        inputnode.means_medians_lists   :   List[Float, Float] OR List[List[Flo,Flo]]
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
        
        # Apply warp to best
        applywarp = pe.MapNode(
            name='applywarp',
            interface=fsl.ApplyWarp(),
            iterfield=['in_file', 'field_file', 'out_file'])
            
        if fsl.no_fsl():
            warn('NO FSL found')
        else:
            applywarp.inputs.ref_file = fsl.Info.standard_image(
                "FMRIB58_FA_1mm.nii.gz")
        
        # Merge the FA files into a 4D file
        mergefa = pe.Node(
            name='mergefa',
            interface=fsl.Merge(dimension='t'))
            
        # Take the mean over the fourth dimension
        meanfa = pe.Node(
            name='meanfa',
            interface=fsl.ImageMaths(
                op_string="-Tmean",
                suffix="_mean"))
                
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
            
        if target == 'best':
            # Find best target that limits mean deformation, insert before applywarp
            fb = self.create_find_best(name='find_best', mask=mask_best)
            
            rename2target = pe.MapNode(
                name='rename2target',
                interface=Function(
                    # seems to be input alphabetically, sep is only named kwarg
                    # arg0=input_id, arg1=to, arg2=target_id, arg3=suffix
                    input_names=['sep', 'arg0', 'arg1', 'arg2', 'arg3'],
                    output_names=['string'],
                    function=join_strs),
                iterfield=['arg0'])
            rename2target.inputs.sep = '_'
            rename2target.inputs.arg1 = 'to'
            if suffix is None:
                suffix = 'inMNI_warp.nii.gz'
            rename2target.inputs.arg3 = suffix
            
            def best2merged(best_id):
                return '_'.join(
                    ('best', 
                     best_id,
                     'inMNI',
                     'warp_merged.nii.gz'))
                
            tbss3.connect([
                (inputnode, fb, 
                    [('fa_list', 'inputnode.fa_list'),
                     ('field_list', 'inputnode.fields_lists'),
                     ('id_list', 'inputnode.id_list'),
                     ('means_medians_lists', 'inputnode.means_medians_lists')]),
                (inputnode, rename2target, 
                    [('id_list', 'arg0')]),
                (inputnode, applywarp, 
                    [('fa_list', 'in_file')]),
                (fb, rename2target, [('outputnode.best_id', 'arg2')]),
                (fb, mergefa, [(('outputnode.best_id', 
                                best2merged), 
                                'merged_file')]),
                (fb, applywarp, 
                    [('outputnode.2best_fields_list', 'field_file'),
                     ('outputnode.best_fa2MNI_mat', 'postmat')]),
                (rename2target, applywarp, 
                    [('string', 'out_file')])
            ])
        elif target == 'FMRIB58_FA_1mm.nii.gz':
            tbss3.connect([
                (inputnode, applywarp, 
                    [("fa_list", "in_file"),
                     ("field_list", "field_file")])
                ])

        # Create outputnode
        outputnode = pe.Node(
            name='outputnode',
            interface=IdentityInterface(
                fields=[
                    'groupmask_file',
                    'skeleton_file',
                    'meanfa_file',
                    'mergefa_file']))
            
        tbss3.connect([
            (applywarp, mergefa, [("out_file", "in_files")]),
            (mergefa, groupmask, [("merged_file", "in_file")]),
            (mergefa, maskgroup, [("merged_file", "in_file")]),
            (groupmask, maskgroup, [("out_file", "in_file2")]),
            ])
            
        if estimate_skeleton:
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
            # $FSLDIR/bin/fslmaths $FSLDIR/data/standard/FMRIB58_FA_1mm -mas mean_FA_mask mean_FA
            maskstd = pe.Node(
                name='maskstd',
                interface=fsl.ImageMaths(
                    op_string="-mas",
                    suffix="_masked"))
            maskstd.inputs.in_file = fsl.Info.standard_image("FMRIB58_FA_1mm.nii.gz")

            # $FSLDIR/bin/fslmaths mean_FA -bin mean_FA_mask
            binmaskstd = pe.Node(
                name='binmaskstd',
                interface=fsl.ImageMaths(op_string="-bin"))

            # $FSLDIR/bin/fslmaths all_FA -mas mean_FA_mask all_FA
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

            outputnode.inputs.skeleton_file = \
                fsl.Info.standard_image("FMRIB58_FA-skeleton_1mm.nii.gz")
            
            tbss3.connect([
                (binmaskstd, outputnode, [('out_file', 'groupmask_file')]),
                (maskstd, outputnode, [('out_file', 'meanfa_file')]),
                (maskgroup2, outputnode, [('out_file', 'mergefa_file')])
                ])
                
        return tbss3
