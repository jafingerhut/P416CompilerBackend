import logging
import ConfigurationConstants as ConfConst
from DependencyAnlyzer.dependencyGraphBuilder import P4ProgramGraph, P4ProgramNode, PipelineID, P4ProgramNodeType, \
    ExpressionNode
from P4ProgramParser.PktGenParser.p4_top import P4_Top
from P4ProgramParser.PktGenParser.util.visualization import generate_graphviz_graph
from utils import JsonParserUtil
from P4ProgramParser.P416Bmv2JsonParser import  P416JsonParser
import DependencyAnlyzer.dependencyGraphBuilder as dgb
import networkx as nx

logger = logging.getLogger('MAIN')
hdlr = logging.FileHandler(ConfConst.LOG_FILE_PATH )
hdlr.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s','%m-%d %H:%M:%S')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logging.StreamHandler(stream=None)
logger.setLevel(logging.INFO)
import matplotlib.pyplot as plt

def dfs_depth(G, source=None, depth_limit=None):
    if source is None:
        nodes = G
    else:
        nodes = [source]
    visited = set()
    if depth_limit is None:
        depth_limit = len(G)
    for start in nodes:
        print(start)
        if start in visited:
            continue
        max_depth = 0
        visited.add(start)
        stack = [(start, depth_limit, iter(G[start]))]
        while stack:
            parent, depth_now, children = stack[-1]
            try:
                child = next(children)
                if child not in visited:
                    yield parent, child
                    visited.add(child)
                    if depth_now > 1:
                        if((depth_limit - depth_now + 1)>max_depth):
                            max_depth = depth_limit - depth_now + 1
                        stack.append((child, depth_now - 1, iter(G[child])))
            except StopIteration:
                stack.pop()
    global max_d
    max_d.append(max_depth)

def loadP416JsonUsingAutoGeneratedJsonParser(file_path):
    rawJsonObjects =  JsonParserUtil.loadRowJsonAsDictFromFile(file_path)
    if((rawJsonObjects == None) ):
        logger.info("Failed to load P4 Json :"+file_path+" Exiting!!!")
        exit(1)
    prorgam = P416JsonParser.ParsedP416Program_from_dict(rawJsonObjects)
    logger.info(prorgam)
    return prorgam

def loadP416JsonUsingPktGenParser(file_path="Resources/P416Programs/leaf.json"):
    top = P4_Top()
    top.load_json_file(file_path)
    top.build_graph(ingress=True, egress=True)
    graph_lcas = {}
    generate_graphviz_graph(top.in_pipeline, top.in_graph, lcas=graph_lcas)
    generate_graphviz_graph(top.eg_pipeline, top.eg_graph)
    print("Hello world")


# loadP416JsonUsingPktGenParser()

print("Hello world")
program = loadP416JsonUsingAutoGeneratedJsonParser(file_path="Resources/P416Programs/spine.json")
programGraph = P4ProgramGraph(program)
programGraph.buildHeaderVector()
# programGraph.preProcessAllActions()
programGraph.loadGraph()

programGraph.headeranalyzer()

# -----------expression node expansion
# testExpNode = ExpressionNode(p4Node = programGraph.pipelineIdToPipelineGraphMap[PipelineID.INGRESS_PIPELINE].pipeline.conditionals[3].expression, p4NodeType = P4ProgramNodeType.CONDITIONAL_NODE, pipelineID=PipelineID.INGRESS_PIPELINE)
# root, smallGraph = testExpNode.expressionToSubgraph()
# print(smallGraph.number_of_nodes())
# print("Graph Depth is "+str(len(nx.dag_longest_path(smallGraph))))
# print("Leaf node list "+str(testExpNode.getAllFieldList()))
#

# print(list(smallGraph.predecessors(root)))
# print(list(smallGraph.successors(root)))
# print(list(smallGraph.reverse().predecessors(root)))
# print(list(smallGraph.reverse().successors(root)))


# conditionalObj = programGraph.pipelineIdToPipelineGraphMap[PipelineID.EGRESS_PIPELINE].pipeline.conditionals[13]
# testExpNode = ExpressionNode(p4Node = conditionalObj.expression, name =conditionalObj.name+"_expr",  p4NodeType = P4ProgramNodeType.CONDITIONAL_NODE, pipelineID=PipelineID.INGRESS_PIPELINE)
# root, smallGraph = testExpNode.expressionToSubgraph()
# plt.subplot(111)
# nx.draw(smallGraph, with_labels=False, font_weight='bold')
# plt.show()
# # nx.draw(smallGraph, with_labels=True, font_wei
# # ght='bold')
# val = testExpNode.getAllFieldList()
# print(str(val))
#
# val = testExpNode.getOnlyModifiedFieldList()
# print(str(val))


