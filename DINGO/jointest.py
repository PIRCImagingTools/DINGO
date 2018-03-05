from nipype.pipeline.engine.tests.test_join import *

def make_multiple_join_nodes_workflow(n):
    """copied from join node unit test 'test_multiple_join_nodes' . """
    # Make the workflow.
    wf = pe.Workflow(name='test%d_element_iterable'%n)
    # the iterated input node
    inputspec = pe.Node(IdentityInterface(fields=['n']), name='inputspec')
    inputspec.iterables = [('n', [1,2])]
    # a pre-join node in the iterated path
    pre_join1 = pe.Node(IncrementInterface(), name='pre_join1')
    wf.connect(inputspec, 'n', pre_join1, 'input1')
    # the first join node
    join1 = pe.JoinNode(IdentityInterface(fields=['vector']),
                        joinsource='inputspec', joinfield='vector',
                        name='join1')
    wf.connect(pre_join1, 'output1', join1, 'vector')
    # an uniterated post-join node
    post_join1 = pe.Node(SumInterface(), name='post_join1')
    wf.connect(join1, 'vector', post_join1, 'input1')
    # the downstream join node connected to both an upstream join
    # path output and a separate input in the iterated path
    join2 = pe.JoinNode(IdentityInterface(fields=['vector', 'scalar']),
                        joinsource='inputspec', joinfield='vector',
                        name='join2')
    wf.connect(pre_join1, 'output1', join2, 'vector')
    wf.connect(post_join1, 'output1', join2, 'scalar')
    # a second post-join node
    post_join2 = pe.Node(SumInterface(), name='post_join2')
    wf.connect(join2, 'vector', post_join2, 'input1')
    # a third post-join node
    post_join3 = pe.Node(ProductInterface(), name='post_join3')
    wf.connect(post_join2, 'output1', post_join3, 'input1')
    wf.connect(join2, 'scalar', post_join3, 'input2')

    return wf


single_wf = make_multiple_join_nodes_workflow(5)
#single_wf.run() # This works


metawf = pe.Workflow(name="meta")
metawf.add_nodes([make_multiple_join_nodes_workflow(m) for m in [5,6]])
metawf.run() # this crashes
