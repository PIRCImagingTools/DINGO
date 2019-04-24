import os
from DINGO.base import (DINGOFlow, DINGONode)
from DINGO.interfaces.dsistudio import (DSIStudioSource,
                                        DSIStudioReconstruct,
                                        DSIStudioTrack,
                                        DSIStudioAnalysis,
                                        DSIStudioExport)
from DINGO.utils import tobool
from DINGO.workflows.utils import HelperFlow
from nipype import (config, IdentityInterface, Function)
from nipype.interfaces import fsl
import nipype.pipeline.engine as pe
from nipype.pipeline.engine.utils import _parameterization_dir
from tempfile import mkdtemp


class HelperDSI(HelperFlow):
    def __init__(self, **kwargs):
        wfm = {
            'DSI_SRC':  'DINGO.DSI_Studio',
            'REC_prep': 'DINGO.DSI_Studio',
            'DSI_REC':  'DINGO.DSI_Studio',
            'DSI_TRK':  'DINGO.DSI_Studio',
            'DSI_ANA':  'DINGO.DSI_Studio',
            'DSI_EXP':  'DINGO.DSI_Studio'
        }
        super(HelperDSI, self).__init__(workflow_to_module=wfm, **kwargs)


class DSI_SRC(DINGONode):
    """Nipype node to create a src file in DSIStudio with dwi, bval, bvec
    
    Parameters
    ----------
    name        :   Str (workflow name, default 'DSI_SRC')
    inputs      :   Dict (Node InputName=ParameterValue)
    **kwargs    :   Workflow InputName=ParameterValue
    
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
        'source':   ['FileIn', 'dti'],
        'bval':     ['FileIn', 'bval'],
        'bvec':     ['FileIn', 'bvec']
    }
    
    def __init__(self, name="DSI_SRC", inputs=None, **kwargs):
        if inputs is None:
            inputs = {}
        super(DSI_SRC, self).__init__(
            name=name, 
            interface=DSIStudioSource(**inputs),
            **kwargs)
            
            
class REC_prep(DINGONode):
    """Nipype node to erode the BET mask (over-inclusive) to pass to DSI_REC"""

    connection_spec = {
        'in_file':  ['BET', 'mask_file']
    }
    
    def __init__(self, name="REC_prep",
                 inputs=None, **kwargs):
        if inputs is None:
            inputs = {}
        if 'op_string' not in inputs:
            inputs['op_string'] = '-ero'
        if 'suffix' not in inputs:
            inputs['suffix'] = '_ero'
        super(REC_prep, self).__init__(
            name=name, 
            interface=fsl.ImageMaths(**inputs),
            **kwargs)


class DSI_REC(DINGONode):
    """Nipype node to create a fib file in DSIStudio with src file
    
    Parameters
    ----------
    name        :     Str (workflow name, default 'DSI_REC')
    inputs      :    Dict (REC node InputName=ParameterValue)
    **kwargs    :    Workflow InputName=ParameterValue
    
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
        'source':   ['DSI_SRC', 'output'],
        'mask':     ['REC_prep', 'out_file']
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
    @staticmethod
    def tract_name_dir(param):
        """Return a reduced parameterization for output directory"""
        if '_tract_names' in param:
            return param[param.index('_tract_names'):]
        return param
            
    def output_dir(self):
        """Return the location of the output directory with tract name, 
        not tract inputs
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
            params_str = [TRKnode.tract_name_dir(p) for p in params_str]
            if not tobool(self.config['execution']['parameterize_dirs']):
                params_str = [_parameterization_dir(p) for p in params_str]
            outputdir = os.path.join(outputdir, *params_str)
            
        self._output_dir = os.path.abspath(os.path.join(outputdir, self.name))
        return self._output_dir    


class DSI_TRK(DINGOFlow):
    """Nipype wf to create a trk with fiber file and input parameters
    DSIStudioTrack.inputs will not seem to reflect the config until
    self._check_mandatory_inputs(), part of run() and cmdline(), is executed
    But, the data will be in the indict field.
    
    Parameters
    ----------
    name        :   Str (workflow name, default 'DSI_TRK')
    inputs      :   Dict Track Node InputName=ParameterValue
        (Inputs['tracts'] is used specially as an iterable, other params
        will apply to each tract)
    **kwargs    :   Workflow InputName=ParameterValue
        any unspecified tractography parameters will be defaults of DSIStudioTrack
                    
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
            
    inputnode = 'inputnode'
    outputnode = 'trknode'
    
    connection_spec = {
        'fib_file': ['DSI_REC', 'fiber_file'],
        'regions':  ['FileIn_SConfig', 'regions']
    }

    def __init__(self, name="DSI_TRK", inputs=None, **kwargs):
        if inputs is None:
            inputs = {}
        
        super(DSI_TRK, self).__init__(name=name, **kwargs)
        
        # Parse inputs
        inputnode = pe.Node(
            name='inputnode',
            interface=IdentityInterface(
                fields=[
                    'fib_file',
                    'tract_names', 
                    'tract_inputs', 
                    'regions']))
        
        if 'tracts' not in inputs:
            if 'rois' not in inputs:
                # config specifies no tracts
                raise KeyError(
                    'CANNOT TRACK! Neither "tracts" nor "rois" in inputs.')
            else:
                # config specifies one tract
                inputnode.inputs.tract_inputs = inputs
        else:
            # config specifies one or more tracts
            # Get universal params, but where overlap want to use tract specific
            univ_keys = inputs.keys()
            univ_keys.remove('tracts')
            univ_inputs = {key: inputs[key] for key in univ_keys}
            for tract in inputs['tracts'].iterkeys():
                for k, v in univ_inputs.iteritems():
                    if k not in inputs['tracts'][tract]:
                        inputs['tracts'][tract].update({k: v})

            inputnode.iterables = [
                ('tract_names', inputs['tracts'].keys()),
                ('tract_inputs', inputs['tracts'].values())]
            inputnode.synchronize = True
            
        # Substitute region names for actual region files
        replace_regions = TRKnode(
            name='replace_regions',
            interface=Function(
                input_names=['tract_input', 'regions'],
                output_names=['real_region_tract_input'],
                function=self.replace_regions))
        
        cfg = dict(execution={'remove_unnecessary_outputs': False})
        config.update_config(cfg)
        # DSI Studio will only accept 5 ROIs or 5 ROAs. A warning would
        # normally be shown that only the first five listed will be used,
        # but merging the ROAs is viable.
        merge_roas = self.create_merge_roas(name='merge_roas')

        trknode = TRKnode(
            name="trknode",
            interface=DSIStudioTrack())
            
        self.connect([
            (inputnode, trknode, 
                [('fib_file', 'source'),
                 ('tract_names', 'tract_name')]),
            (inputnode, replace_regions, 
                [('tract_inputs', 'tract_input'),
                 ('regions', 'regions')]),
            (inputnode, merge_roas,
                [('tract_names', 'inputnode.tract_name')]),
            (replace_regions, merge_roas,
                [('real_region_tract_input', 'inputnode.tract_input')]),
            (merge_roas, trknode, 
                [('outputnode.mroas_tract_input', 'indict')])
        ])
            
    def replace_regions(tract_input=None, regions=None):
        """Return the right regions needed by tract_input"""
        import re
        if regions is not None:
            # without per subject region list the analysis config must have
            # filepaths for region lists, thus can only work in one space
            region_types = ('rois', 'roas', 'seed', 'ends', 'ter')
            for reg_type in region_types:
                if reg_type in tract_input:
                    regionname_list = tract_input[reg_type]
                    region_files = []
                    for regionname in regionname_list:
                        # match pattern preceded by '\' or '_' or '/'
                        pattern = ''.join(('(?<=[\\\\_\/])', regionname))
                        found = False
                        for realregion in regions:  # realregion is a filepath
                            if re.search(pattern, realregion, flags=re.IGNORECASE):
                                region_files.append(realregion)
                                found = True
                                break
                        if not found:
                            raise Exception('{} not found in region file list'
                                            .format(regionname))
                    if len(region_files) != len(regionname_list):
                        raise Exception('Incorrect number of regions found')
                    tract_input.update({reg_type: region_files})
        return tract_input
                                
    def create_merge_roas(self, name='merge_roas'):
        """Create nipype workflow that will merge roas in tract_input"""
        merge = pe.Workflow(name=name)
        
        inputnode = pe.Node(
            name='inputnode',
            interface=IdentityInterface(
                fields=['tract_input', 'tract_name']),
            mandatory_inputs=True)
            
        def merge_roas(tract_input, tract_name):
            """Function to merge roas into one image, used as node"""
            from DINGO.workflows.dsistudio import TRKnode
            import nipype.interfaces.fsl as fsl
            import os
            if 'roas' in tract_input and len(tract_input['roas']) > 5:
                roa_list = tract_input['roas']
                if not isinstance(roa_list, list):
                    roa_list = [roa_list]
                merged_filename = ''.join((tract_name, '_mergedroas', '.nii.gz'))
                
                mergenode = TRKnode(
                    base_dir=os.getcwd(),
                    name='mergenode',
                    interface=fsl.Merge(in_files=roa_list, 
                                        merged_file=merged_filename,
                                        dimension='t'))
                merge_result = mergenode.run()
                mroas = merge_result.outputs.merged_file
                
                maxnode = TRKnode(
                    base_dir=os.getcwd(),
                    name='maxnode',
                    interface=fsl.ImageMaths(in_file=mroas, op_string='-Tmax'))
                max_result = maxnode.run()
                mmroas = max_result.outputs.out_file
                tract_input.update({'roas': mmroas})
            # Unsure if nipype function copies or passes dicts, to be safe returning it
            return tract_input
            
        merge_roas_node = TRKnode(
            name='merge_roas',
            interface=Function(
                input_names=['tract_input', 'tract_name'],
                output_names=['mroas_tract_input'],
                function=merge_roas))
            
        outputnode = pe.Node(
            name='outputnode',
            interface=IdentityInterface(
                fields=['mroas_tract_input']))
                
        merge.connect([
            (inputnode, merge_roas_node, 
                [('tract_input', 'tract_input'),
                 ('tract_name', 'tract_name')]),
            (merge_roas_node, outputnode,
                [('mroas_tract_input', 'mroas_tract_input')])
        ])
        
        return merge
        

class DSI_ANA(DINGOFlow):
    """Nipype node to run DSIStudioAnalysis
    
    Parameters
    ----------
    name    :    Str (node name, default 'DSI_ANA')
    inputs  :    Dict (DSIStudioAnalysis Node InputName=ParameterValue)
    kwargs  :    (Nipype node InputName=ParameterValue)
    
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
    inputnode = 'ananode'
    outputnode = 'ananode'
    
    def __init__(self, name='DSI_ANA', inputs={}, **kwargs):
        super(DSI_ANA, self).__init__(name=name, **kwargs)
        
        ananode = pe.MapNode(
            name='ananode',
            interface=DSIStudioAnalysis(**inputs),
            iterfield=['tract'])
        self.add_nodes([ananode])


class DSI_ANAnode(DINGONode):
    def __init__(self, name='DSI_ANA', inputs={}, **kwargs):
        super(DSI_ANAnode, self).__init__(
            name=name,
            interface=DSIStudioAnalysis(**inputs),
            **kwargs)


class DSI_Merge(DINGOFlow):
    """Nipype workflow to merge tracts with specified names
    """
    inputnode = 'inputnode'
    outputnode = 'outputnode'

    connection_spec = {
        'tract_list': ['DSI_TRK', 'output']
    }

    def __init__(self,
                 name='DSI_Merge',
                 inputs=None,
                 **kwargs):
        if inputs is None:
            inputs = {}
        super(DSI_Merge, self).__init__(name=name, **kwargs)

        if 'req_join' in inputs and inputs['req_join'] is not None:
            req_join = inputs['req_join']
            del inputs['req_join']
        else:
            req_join = False

        if req_join:
            inputnode = pe.JoinNode(
                name='inputnode',
                interface=IdentityInterface(
                    fields=['tract_list',
                            'tract_names',
                            'tracts2merge',
                            'source']),
                mandatory_inputs=True,
                joinsource=self.setup_inputs,
                joinfield=['tract_list'])
        else:
            inputnode = pe.Node(
                name='inputnode',
                interface=IdentityInterface(
                    fields=['tract_list',
                            'tract_names',
                            'tracts2merge',
                            'source']),
                mandatory_inputs=True)

        if 'source' in inputs and inputs['source'] is not None:
            inputnode.inputs.source = inputs['source']
        if 'tract_list' in inputs and inputs['tract_list'] is not None:
            inputnode.inputs.tract_list = inputs['tract_list']
            del inputs['tract_list']
        inputnode.iterables = [
            ('tract_names', inputs['tracts'].keys()),
            ('tracts2merge', inputs['tracts'].values())]
        del inputs['tracts']
        inputnode.synchronize = True

        replace_tracts = TRKnode(
            name='replace_tracts',
            interface=Function(
                input_names=['tract_list',
                             'tracts2merge'],
                output_names=['tract_files'],
                function=self.replace_tracts))

        convertnode = pe.MapNode(
            name='convertnode',
            interface=DSIStudioAnalysis(**inputs),
            iterfield=['tract'])

        mergenode = TRKnode(
            name='merge_tracts',
            base_dir=os.getcwd(),
            interface=Function(
                input_names=['file_list',
                             'tracts2merge',
                             'new_tract_name'],
                output_names=['merged_file'],
                function=self.merge_tracts))

        outputnode = TRKnode(
            name='outputnode',
            interface=IdentityInterface(
                fields=['merged_file']))

        self.connect([
            (inputnode, replace_tracts, [('tract_list', 'tract_list'),
                                         ('tracts2merge', 'tracts2merge')]),
            (inputnode, convertnode, [('source', 'source')]),
            (inputnode, mergenode, [('tract_names', 'new_tract_name'),
                                    ('tracts2merge', 'tracts2merge')]),
            (replace_tracts, convertnode, [('tract_files', 'tract')]),
            (convertnode, mergenode, [('output', 'file_list')]),
            (mergenode, outputnode, [('merged_file', 'merged_file')])
        ])

    def replace_tracts(tract_list, tracts2merge):
        """Return the real tract files from the tract list
        which match the names in tracts2merge.
        Raise Exception if none are found.

        Parameters
        ----------
        tracts2merge    :   Sequence(Str, Str, ...)
        tract_list      :   Sequence(Str, Str, Str, ...)

        Returns
        -------
        tract_files     :   Sequence(Str, Str, ...)
        """
        import re
        import os
        if not isinstance(tract_list, (list, tuple)):
            tract_list = [tract_list]
        tract_files = []
        if tracts2merge is not None:
            for tractname in tracts2merge:
                pattern = ''.join(('(?<=[\\\\_\/])', tractname))
                for realtract in tract_list:  # realtract is a filepath
                    if re.search(pattern, realtract, flags=re.IGNORECASE):
                        tract_files.append(realtract)
                        break
            if len(tract_files) == 0:
                raise Exception('No tracts found matching any of {}'
                                .format(tracts2merge))
            else:
                new_tracts2merge = []
                basenames = [os.path.basename(afile) for afile in tract_files]
                for aname in tracts2merge:
                    if any((aname in afile for afile in basenames)):
                        new_tracts2merge.append(aname)
        return tract_files

    def merge_tracts(file_list=None, tracts2merge=None, new_tract_name=None):
        """Accept tract files in '.txt' format, each line a stream. Return merged"""
        import os
        merged_data = []
        try:
            for idx in xrange(len(file_list)):
                with open(file_list[idx], 'r') as f:
                    merged_data.extend(f.readlines())
            basename = os.path.basename(file_list[0])
            old = tracts2merge[
                [tract in basename for tract in tracts2merge]
                .index(True)]
            merged_filename = basename.replace(
                old, new_tract_name)
            merged_file = os.path.abspath(merged_filename)
            with open(merged_file, 'w') as f:
                f.writelines(merged_data)
        except TypeError:
            merged_file = None
        return merged_file


class DSI_EXP(DINGONode):
    """Nipype node to run DSIStudioAnalysis
    
    Parameters
    ----------
    name    :    Str (node name, default 'DSI_EXP')
    inputs    :    Dict (DSIStudioExport Node InputName=ParameterValue)
    kwargs    :    (Nipype node InputName=ParameterValue)
    
    Returns
    -------
    Nipype node (name=name, interface=DSIStudioExport(**inputs), **kwargs)
    
    Example
    -------
    dsi_exp = DSI_EXP(name='dsi_exp',
                    inputs={'source' :    'my.fib.gz',\
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
