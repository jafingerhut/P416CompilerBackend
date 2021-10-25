import json
import logging
from enum import Enum
import sys

from networkx.drawing.nx_agraph import to_agraph

from DependencyAnlyzer.DefinitionConstants import P4ProgramNodeType, PipelineID
from DependencyAnlyzer.P4ProgramNode import ExpressionNode, MATNode
from P4ProgramParser.P416JsonParser import Key, SuperTable, Table

sys.path.append("..")
import ConfigurationConstants as confConst



import networkx as nx
logger = logging.getLogger('PipelineGraph')
hdlr = logging.FileHandler(confConst.LOG_FILE_PATH )
hdlr.setLevel(logging.INFO)
# formatter = logging.Formatter('[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s','%m-%d %H:%M:%S')
formatter = logging.Formatter('%(message)s','%S')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logging.StreamHandler(stream=None)
logger.setLevel(logging.INFO)

def common_member(a, b):
    a_set = set(a)
    b_set = set(b)

    if (a_set & b_set):
        return(a_set & b_set)
    else:
        return None

class PipelineGraph:
    def __init__(self, pipelineID,pipeline, actions):
        self.pipelineID = pipelineID
        self.dummyStart = None
        self.dummyEnd = None
        self.p4Graph = nx.DiGraph()
        self.p4Graph.add_node(self.dummyStart, label="Start")
        self.p4Graph.add_node(self.dummyEnd, label="End")
        self.pipeline = pipeline
        self.matchDependencyMap = {}
        self.actionDependencyMap = {}
        self.succesorDependencyMap = {}
        self.reverseMatchDependencyMap = {}
        self.alreadyLoadedTables={}
        self.nameToP4NodeMap ={}
        self.actions = actions
        self.registerNameToTableMap = {}
        self.superTableNameToSubTableListMap= {}
        self.registerNameToSuperMatNameMap= {}
        self.conditionalNodes = {}
        self.matchActionNodes= {}
        self.swappedTableMapForStatefulMemoryBasedPreprocessing = {}

    def headeranalyzerForSinglePipeline(self):
        '''
        This function analyze which headers are used in a pipeline. and find what is their total length so that we can split the header fields in 2 different sets
        :param piepelineId:
        :return:
        '''
        #At first analyzig the match action table of the  pipeline
        pipelineObject = self.pipeline
        allHeaderFieldUsedInMatchPartAllMAT = []
        allHeaderFieldUsedInActionsOfAllMAT = []
        for tbl in pipelineObject.tables:
            if(type(tbl) == SuperTable):
                for subTable in tbl.subTableList:
                    allHeaderFieldUsedInOneMAT = subTable.getAllMatchFields()
                    allHeaderFieldUsedInActionsOfOneMAT = self.getAllFieldsModifedInActionsOfTheTable(subTable.name)
                    if len(allHeaderFieldUsedInOneMAT)>0:
                        for e in allHeaderFieldUsedInOneMAT:
                            allHeaderFieldUsedInMatchPartAllMAT.append(e)
                    if len(allHeaderFieldUsedInActionsOfOneMAT)>0:
                        for e in allHeaderFieldUsedInActionsOfOneMAT:
                            allHeaderFieldUsedInActionsOfAllMAT.append(e)

            else:
                allHeaderFieldUsedInOneMAT = tbl.getAllMatchFields()
                allHeaderFieldUsedInActionsOfOneMAT = self.getAllFieldsModifedInActionsOfTheTable(tbl.name)
                if len(allHeaderFieldUsedInOneMAT)>0:
                    for e in allHeaderFieldUsedInOneMAT:
                        allHeaderFieldUsedInMatchPartAllMAT.append(e)
                if len(allHeaderFieldUsedInActionsOfOneMAT)>0:
                    for e in allHeaderFieldUsedInActionsOfOneMAT:
                        allHeaderFieldUsedInActionsOfAllMAT.append(e)

        print("Before removing duplicate member of match fields "+str(len(allHeaderFieldUsedInMatchPartAllMAT)))
        allHeaderFieldUsedInMatchPartAllMAT = set(allHeaderFieldUsedInMatchPartAllMAT) # removing duplicate through set operations. Becuase multiple MAT can use same header fileds.
        print("After removing duplicate member  of match fields "+str(len(allHeaderFieldUsedInMatchPartAllMAT)))
        print(allHeaderFieldUsedInMatchPartAllMAT)
        print("Before removing duplicate member of action fields "+str(len(allHeaderFieldUsedInActionsOfAllMAT)))
        allHeaderFieldUsedInActionsOfAllMAT = set(allHeaderFieldUsedInActionsOfAllMAT) # removing duplicate through set operations. Becuase multiple MAT can use same header fileds in their actions.
        print("After removing duplicate member  of match fields "+str(len(allHeaderFieldUsedInActionsOfAllMAT)))
        fullListOfHeaderFieldsUsedInThePipeline= allHeaderFieldUsedInMatchPartAllMAT.union(allHeaderFieldUsedInActionsOfAllMAT)
        print("Total number of header fields used in the pipeline is "+str(len(fullListOfHeaderFieldsUsedInThePipeline)))

        #Now analyzig the conditionals of the pipeline
        allHeaderFieldUsedInConditionCheckingPartOfAllConditionals = []
        for conditionalObj in pipelineObject.conditionals:
            exprNode = ExpressionNode(parsedP4Node = conditionalObj.expression, name =conditionalObj.name,  parsedP4NodeType = P4ProgramNodeType.CONDITIONAL_NODE, pipelineID=self.pipelineID)
            allHeaderFieldUsedInConditionCheckingPartOfOneConditionals = exprNode.getAllFieldList()
            if len(allHeaderFieldUsedInConditionCheckingPartOfOneConditionals)>0:
                for e in allHeaderFieldUsedInConditionCheckingPartOfOneConditionals:
                    allHeaderFieldUsedInConditionCheckingPartOfAllConditionals.append(e)
        print("Before removing duplicate member of conditional checking of all the conditional  "+str(len(allHeaderFieldUsedInConditionCheckingPartOfAllConditionals)))
        allHeaderFieldUsedInConditionCheckingPartOfAllConditionals = set(allHeaderFieldUsedInConditionCheckingPartOfAllConditionals) # removing duplicate through set operations. Becuase multiple MAT can use same header fileds.
        print("After removing duplicate member of conditional checking of all the conditional  "+str(len(allHeaderFieldUsedInConditionCheckingPartOfAllConditionals)))
        #Condtioanls have either true or false. they do not have own action. their true_next or false_next is an action. These acrions are analyzed with match-action tables.
        #So need to proces them again
        fullListOfHeaderFieldsUsedInThePipeline = allHeaderFieldUsedInConditionCheckingPartOfAllConditionals.union(fullListOfHeaderFieldsUsedInThePipeline)
        print("Total number of header fields used in the pipeline is "+str(len(fullListOfHeaderFieldsUsedInThePipeline)))
        return fullListOfHeaderFieldsUsedInThePipeline

    def getAllFieldsModifedInActionsOfTheTable(self, tblName):
        tbl = self.pipeline.getTblByName(tblName)
        if(tbl == None):
            return []
        totalFieldList = []
        for a in tbl.actions:
            act = self.getActionByName(a)
            if (act != None):
                newfieldList = act.getListOfFieldsModifedAndUsed()[0]
                totalFieldList = totalFieldList + newfieldList
        return totalFieldList

    def getActionByName(self, actName):
        for act in self.actions:
            if(act.name == actName):
                return act
        return None

    def preProcessPipelineGraph(self):
        # self.traverseTDG()
        # print(len(self.pipeline.tables))
        self.preprocessConditionalNodeRecursively(self.pipeline.init_table, confConst.DUMMY_START_NODE)
        # print(self.pipeline.tables)
        # print("Drawing graph after conditiona processing ")
        self.drawPipeline("./"+str(self.pipelineID)+"_afterConditioanlProcessing.png")
        # # print(len(self.pipeline.tables))
        self.iterativelyPreprocessMATAccessingStatefuleMemmories()
        # # print(len(self.pipeline.tables))
        # # print("\n\n\n")
        # # print(self.pipeline.tables)
        # # print("Drawing graph after stateful memory processing ")
        self.drawPipeline("./"+str(self.pipelineID)+"_afterStatefulMemoeryProcessing.png")

    def traverseTDG(self):
        nodeList = []
        self.traverseTDGRecursivelyBeforeCreatingSuperMat(self.pipeline.init_table, nodeList)
        pass

    def traverseTDGRecursivelyBeforeCreatingSuperMat(self, name, nodeList):
        # if(name==None):
        #     print("None")
        #     # logger.info(nodeList)
        #     return
        # else:
        #     print(name)
        tbl = self.pipeline.getTblByName(name)
        conditional = self.pipeline.getConditionalByName(name)
        nodeList.append(name)
        if(tbl != None):
            if(tbl.is_visited_for_conditional_preprocessing == True):
                return
            if(len(tbl.next_tables.keys())<=0):
                print(nodeList)
            for tblKey in list(tbl.next_tables.keys()):
                nxtNode = tbl.next_tables.get(tblKey)
                newNodeList = [n for n in nodeList]
                self.traverseTDGRecursivelyBeforeCreatingSuperMat(nxtNode, newNodeList)
            tbl.is_visited_for_conditional_preprocessing = True
            return
        elif(conditional != None):
            next_tables = [conditional.true_next, conditional.false_next]
            if(len(next_tables)<=0):
                print(nodeList)
            for nxtNode in next_tables:
                newNodeList = [n for n in nodeList]
                self.traverseTDGRecursivelyBeforeCreatingSuperMat(nxtNode, newNodeList)
            conditional.is_visited_for_conditional_preprocessing = True
            return

    def iterativelyPreprocessMATAccessingStatefuleMemmories(self):
        # print("inside iterativelyPreprocessMATAccessingStatefuleMemmories")
        #check if two super mat have something common. on that case refer them to same supetMat. that super matname will be used
        #for both registers. and all the sub table used by these two registers will be in merged into one list.
        #do this in a n^2 loop .
        # todo in later stage, we have to check if two actions access the memories in opposite order than there will be troyble. we can not embed the programs
        regNameTobePopped = []
        combinedRegNameToBeAdded = {}
        for reg1 in self.registerNameToTableMap.keys():
            reg1TblList = self.registerNameToTableMap.get(reg1)
            for reg2 in self.registerNameToTableMap.keys():
                reg2TblList = self.registerNameToTableMap.get(reg2)
                if(reg1TblList != None) and (reg2TblList!= None) and (reg1 != reg2):
                    if(common_member(reg1TblList, reg2TblList)!= None):
                        combinedSubTbleList = reg1TblList + reg2TblList
                        combinedRegName = reg1+reg2
                        self.registerNameToTableMap[reg1] = None
                        self.registerNameToTableMap[reg2] = None
                        combinedRegNameToBeAdded[combinedRegName] = combinedSubTbleList
                        regNameTobePopped.append(reg1)
                        regNameTobePopped.append(reg2)
        for regName in regNameTobePopped:
            self.registerNameToTableMap.pop(regName) #Just removing the register whi were combined in the previous step
        for combinedRegName in combinedRegNameToBeAdded.keys():
            combinedSubTbleList = combinedRegNameToBeAdded.get(combinedRegName)
            self.registerNameToTableMap[combinedRegName] = combinedSubTbleList
            print("Adding :"+combinedRegName+" and list is "+str(combinedSubTbleList))
        #==================================== The previous part is required for handling multiple stateful memory access by multiple  action
        for regName in self.registerNameToTableMap.keys():
            superMatName = confConst.SUPER_MAT_PREFIX+regName
            self.superTableNameToSubTableListMap[superMatName] = []
            self.registerNameToSuperMatNameMap[regName] = superMatName
            #TODO If any two super mat have common subtable list then it means ehy need to be embedded together. so

        for regName in self.registerNameToSuperMatNameMap.keys():
            superMatName = self.registerNameToSuperMatNameMap.get(regName)
            subTableListTobeAdded = []
            superTable = SuperTable(name = superMatName, subTableList = subTableListTobeAdded)
            self.pipeline.tables.append(superTable)
        for regName in self.registerNameToTableMap:
            tableList = self.registerNameToTableMap.get(regName)
            superMatName = self.registerNameToSuperMatNameMap.get(regName)
            # print("super mat name is "+superMatName)
            for regTBLName in tableList:
                for tbl in self.pipeline.tables:
                    if(type(tbl) == SuperTable):
                        # Because at this moment we do not need to process the super tables. they are just initialized with default values. so no need to
                        # process their next references.
                        continue
                    for tk in tbl.next_tables.keys():
                        if tbl.next_tables.get(tk)  == regTBLName:
                            if( (tbl.next_tables.get(tk) in self.superTableNameToSubTableListMap.get(superMatName))):
                                continue
                            else:
                                # print("Next table value to be inserted is "+tbl.next_tables.get(tk))
                                l = self.superTableNameToSubTableListMap.get(superMatName)
                                l.append(tbl.next_tables.get(tk))
                                self.superTableNameToSubTableListMap[superMatName]  = l
                                # print("content of the mapped list is "+str(self.superTableNameToSubTableListMap.get(superMatName)))
                                superTblObject = self.pipeline.getTblByName(superMatName)
                                superTblObject.previousNodeToSubTableMap[tbl.name] = regTBLName
                            tbl.next_tables[tk] = superMatName
                for c in self.pipeline.conditionals:
                    if (regTBLName==c.true_next):
                        # print("Next conditional true value to be inserted is "+c.true_next)
                        if( (c.true_next in self.superTableNameToSubTableListMap.get(superMatName))):
                            continue
                        else:
                            l = self.superTableNameToSubTableListMap.get(superMatName)
                            l.append(c.true_next)
                            self.superTableNameToSubTableListMap[superMatName] = l
                            # print("content of the mapped list is "+str(self.superTableNameToSubTableListMap.get(superMatName)))
                            superTblObject = self.pipeline.getTblByName(superMatName)
                            superTblObject.previousNodeToSubTableMap[c.name] = regTBLName
                    c.true_next = superMatName
                    if (regTBLName==c.false_next):
                        # print("Next conditional false value to be inserted is "+c.false_next)
                        if( (c.false_next in self.superTableNameToSubTableListMap.get(superMatName))):
                            continue
                        else:
                            # print("content of the mapped list before insertion "+str(self.superTableNameToSubTableListMap.get(superMatName)))
                            l = self.superTableNameToSubTableListMap.get(superMatName)
                            l.append(c.false_next)
                            self.superTableNameToSubTableListMap[superMatName] = l
                            # print("content of the mapped list after insertion "+str(self.superTableNameToSubTableListMap.get(superMatName)))
                            superTblObject = self.pipeline.getTblByName(superMatName)
                            superTblObject.previousNodeToSubTableMap[c.name] = regTBLName
                        c.false_next = superMatName


        for regName in self.registerNameToSuperMatNameMap.keys():
            superMatName = self.registerNameToSuperMatNameMap.get(regName)
            subTblList = self.superTableNameToSubTableListMap.get(superMatName)
            # print("Follwoing tables are mapped to the reg:"+regName)
            subTableListTobeAdded = []
            for tbl in subTblList:
                # remove each table from pipeline.table and form a new super table. and insert into pipeline.tables
                # print(tbl)
                removedTable = self.pipeline.removeTableByName(tbl)
                if(removedTable!=None):
                    subTableListTobeAdded.append(removedTable)
            superTable = SuperTable(name = superMatName, subTableList = subTableListTobeAdded)
            self.pipeline.tables.append(superTable)

        # #todo#now remove each of the table frm pipeline table list and form rename and create appropriate supertable with sub table list
        # print("Showing all table name in the pipepline 2")
        # self.pipeline.showAllTableName()
        # print("\n\n\n\n\n")

        print("Showing all table name in the pipepline 3")
        self.pipeline.showAllTableName()
        print("\n\n\n\n\n")



    def preprocessConditionalNodeRecursively(self, nodeName, callernode, toPrint= True ):
        if(nodeName == "node_37"):
            return

        node = self.getNodeWithActionsForConditionalPreProcessing(nodeName)
        prevNode = self.getNodeWithActionsForConditionalPreProcessing(callernode)
        if(node == None):
            # logger.info("No relevant node is found in the pipeline for : " + nodeName)
            return
        if(node.originalP4node.is_visited_for_conditional_preprocessing == True):
            return

        else:

            if (len(node.nextNodes)<=0):
                return
            else:
                for nxtNodeName in node.nextNodes:
                    # print("callernode == \""+callernode+"\" and nodeName ==\""+nodeName+"\" and  nxtNodeName == \""+nxtNodeName+"\"")
                    # if(node.oriiginalP4node.is_visited_for_conditional_preprocessing == True) and (prevNode.oriiginalP4node.is_visited_for_conditional_preprocessing == True):
                    #     print("callernode == \""+callernode+"\" and nodeName ==\""+nodeName+"\" and  nxtNodeName == \""+nxtNodeName+"\"")
                        # return
                    # if nodeName == "node_20" and nxtNodeName == "OntasIngress.hashing_src0_tb":
                    #     print("callernode == \""+callernode+"\" and nodeName ==\""+nodeName+"\" and  nxtNodeName == \""+nxtNodeName+"\"")
                    # print("callernode == \""+callernode+"\" and nodeName ==\""+nodeName+"\" and  nxtNodeName == \""+nxtNodeName+"\"")
                    # if(nxtNodeName == "node_15") :
                    #     print("The nxtNodeName node_15 is coming from node :"+nodeName+" Called from "+callernode)
                    # if(nxtNodeName == "OntasIngress.anony_srcip_tb") :
                    #     print("The nxtNodeName is OntasIngress.anony_srcip_tb is coming from node :"+nodeName+" Called from "+callernode)
                    # if(nxtNodeName == "node_17") :
                    #     print("The nxtNodeName node_17 is coming from node :"+nodeName+" Called from "+callernode)
                    # if(nxtNodeName == "OntasIngress.anony_arp_mac_src_oui_tb") :
                    #     print("The nxtNodeName is OntasIngress.anony_arp_mac_src_oui_tb is coming from node :"+nodeName+" Called from "+callernode)
                    self.preprocessConditionalNodeRecursively(nxtNodeName,nodeName) #inside this function call we have add the headerfield for carrying if-else result
                    node.originalP4node.is_visited_for_conditional_preprocessing =True

        return

    def getNodeWithActionsForConditionalPreProcessing(self, name):
        if(name==None):
            logger.info("Name is None in getNode. returning None")
            return None
        tbl = self.pipeline.getTblByName(name)
        conditional = self.pipeline.getConditionalByName(name)

        if(tbl != None):
            # print("Table name is "+name)
            p4teTableNode =MATNode(nodeType= P4ProgramNodeType.TABLE_NODE, name = name, oriiginalP4node = tbl )
            p4teTableNode.matchKey = tbl.getAllMatchFields()
            p4teTableNode.actions = tbl.actions
            p4teTableNode.actionObjectList = []
            for a in p4teTableNode.actions:
                actionObject = self.getActionByName(a)
                p4teTableNode.actionObjectList.append(actionObject)
                # Todo : get the list of fields modifiede here.
                # print(self.getActionByName(a).getListOfFieldsModifedAndUsed())
                statefulMemoeryBeingUsed = actionObject.getListOfStatefulMemoriesBeingUsed()
                for statefulMem in statefulMemoeryBeingUsed:
                    if(self.registerNameToTableMap.get(statefulMem) == None):
                        self.registerNameToTableMap[statefulMem] = []
                    if (not(name in self.registerNameToTableMap.get(statefulMem))):
                        self.registerNameToTableMap.get(statefulMem).append(name)

            for a in list(tbl.next_tables.values()):
                if(a!=None):
                    nodeList = self.getNextNodeForconditionalPreprocessing(a, self.pipelineID)
                    p4teTableNode.nextNodes = p4teTableNode.nextNodes + nodeList
            return p4teTableNode
        elif(conditional != None):
            # print("conditional name is "+name)
            p4teConditionalNode =MATNode(nodeType= P4ProgramNodeType.CONDITIONAL_NODE , name = name, oriiginalP4node = conditional)
            p4teConditionalNode.exprNode = ExpressionNode(parsedP4Node = conditional.expression, name= name,  parsedP4NodeType = P4ProgramNodeType.CONDITIONAL_NODE, pipelineID=self.pipelineID)
            #p4teConditionalNode.actions = self actions  # A conditional is itself an action so its actions are itself own
            # store the action used in the conditional
            p4teConditionalNode.matchKey = None
            # p4teConditionalNode.actions =
            p4teConditionalNode.next_tables = [conditional.true_next, conditional.false_next]
            for a in p4teConditionalNode.next_tables:
                if(a!=None):
                    nodeList = self.getNextNodeForconditionalPreprocessing(a, isArrivingFromConditional=True)
                    p4teConditionalNode.nextNodes = p4teConditionalNode.nextNodes + nodeList
            return p4teConditionalNode
        pass

    def getNextNodeForStatefulMemoryBasedAnalysis(self, nodeName, isArrivingFromConditional=False):
        nextNodeList = []
        for actionEntry in self.actions:
            if actionEntry.name  == nodeName:
                nextNodeList.append(nodeName)
        for matchTable in self.pipeline.tables:
            if(matchTable.name == nodeName):
                nextNodeList.append(nodeName)
        for cond in self.pipeline.conditionals:
            if cond.name  == nodeName:
                nextNodeList.append(nodeName)
        for nameSwappedTableName in self.swappedTableMapForStatefulMemoryBasedPreprocessing.keys():
            if(nameSwappedTableName == nodeName):
                for matchTable in self.pipeline.tables:
                    if matchTable.name  == nameSwappedTableName:
                        nextNodeList.append(matchTable.name)
        return nextNodeList

    def getNextNodeForconditionalPreprocessing(self, nodeName, isArrivingFromConditional=False):
        nextNodeList = []
        for actionEntry in self.actions:
            if actionEntry.name  == nodeName:
                nextNodeList.append(nodeName)
        for matchTable in self.pipeline.tables:
            if matchTable.name  == nodeName:
                if(self.pipeline.name == PipelineID.INGRESS_PIPELINE.value) and (isArrivingFromConditional == True):
                    # json_object = json.loads(confConst.SPECIAL_KEY_FOR_CARRYING_CODNDITIONAL_RESULT_IN_INGRESS)
                    obj = Key.from_dict(confConst.SPECIAL_KEY_FOR_CARRYING_CODNDITIONAL_RESULT_IN_INGRESS)
                    matchTable.key.append(obj)
                elif (self.pipeline.name == PipelineID.EGRESS_PIPELINE.value)  and (isArrivingFromConditional == True):
                    # json_object = json.loads(confConst.SPECIAL_KEY_FOR_CARRYING_CODNDITIONAL_RESULT_IN_EGRESS)
                    obj = Key.from_dict(confConst.SPECIAL_KEY_FOR_CARRYING_CODNDITIONAL_RESULT_IN_EGRESS)
                    matchTable.key.append(obj)
                nextNodeList.append(nodeName)
        for cond in self.pipeline.conditionals:
            if cond.name  == nodeName:
                nextNodeList.append(nodeName)
        # for nameSwappedTableName in self.swappedTableMapForStatefulMemoryBasedPreprocessing.keys():
        #     if(nameSwappedTableName == nodeName):
        #         for matchTable in self.pipeline.tables:
        #             if matchTable.name  == nameSwappedTableName:
        #                 nextNodeList.append(matchTable.name)
        return nextNodeList

    def drawPipeline(self,filePath= "./before-conditional"):
        self.pipeline.resetIsVisitedVariableForGraphDrawing()
        nxGraph = nx.DiGraph()
        alreadyVisitedNodesMap = {}
        self.getNxGraph(self.pipeline.init_table, nxGraph, pred = confConst.DUMMY_START_NODE,indenter = "", alreadyVisitedNodesMap=alreadyVisitedNodesMap)
        print("\n\n\n printing all nodes int he graph ")
        print(nxGraph.nodes())
        A = to_agraph(nxGraph)

        # print(A)
        for node in nxGraph.nodes():
            n=A.get_node(node)
            n.attr['shape']='box'
            n.attr['style']='filled'
            n.attr['fillcolor']='turquoise'
            # n.attr['node_size']=1
        # A.layout(prog="neato", args="-Nshape=circle -Efontsize=20")
        A.layout('dot',args="-Nshape=circle -Efontsize=20")
        A.draw(filePath)
        pass

    def getNxGraph(self, nodeName, nxGraph, pred, indenter = "\t", alreadyVisitedNodesMap={}):
        # if(nodeName!=None):
        #     print("Adding node in graph"+ nodeName)
        flag = False
        if(nodeName!=None):
            nxGraph.add_nodes_from([(nodeName, {"label" : nodeName,"color": "red"})])
        if(nodeName!=None):
            nxGraph.add_edges_from([(pred, nodeName)], label="")
        tbl = self.pipeline.getTblByName(nodeName)
        conditional = self.pipeline.getConditionalByName(nodeName)
        if ( tbl != None) and (type(tbl)== SuperTable):
            if(tbl.is_visited_for_graph_drawing== True):
                return
            for t in tbl.subTableList:
                if(tbl.is_visited_for_graph_drawing== False):
                    for a in list(t.next_tables.values()):
                        self.getNxGraph(a, nxGraph, nodeName, indenter = indenter+"\t")
                    t.is_visited_for_graph_drawing= True
            tbl.is_visited_for_graph_drawing= True
        elif ( tbl != None):
            if(tbl.is_visited_for_graph_drawing== True):
                return
            for a in list(tbl.next_tables.values()):
                if(a!=None):
                    self.getNxGraph(a, nxGraph, nodeName,indenter+"\t")
            tbl.is_visited_for_graph_drawing= True
        elif(conditional != None):
            if(conditional.is_visited_for_graph_drawing== True):
                return
            next_tables = [conditional.true_next, conditional.false_next]
            for a in next_tables:
                if(a!=None):
                    self.getNxGraph(a, nxGraph, nodeName, indenter+"\t")
            conditional.is_visited_for_graph_drawing= True

    def loadTDG(self, name, predMatNode):
        p4MatNode = self.getMatNodeForTDGProcessing(name)
        # find the correct predeccesor of the p4Node and the deendency type it have with that predecessor
        # if(there is not dependency between the predMatNode and p4MatNode )
        #     then recursively browse all the predecessors of the pred and ascore them in increasing number.
        #     then add the most restricited one as the predecessor of the p4MatNode with the dependnency type
        # otherwise
        #     add the predMatNode as the predecessor of the p4MatNode with relevent dependemcy type as edge attribute.

        # nodeList.append(name)
        # if(p4Node != None) and (p4Node.nodeType== P4ProgramNodeType.TABLE_NODE):
        #     if(p4Node.is_visited_for_TDG_processing == True):
        #         return
        #     for tblKey in list(tbl.next_tables.keys()):
        #         nxtNode = tbl.next_tables.get(tblKey)
        #         newNodeList = [n for n in nodeList]
        #         self.traverseTDGRecursivelyBeforeCreatingSuperMat(nxtNode, newNodeList)
        #     tbl.is_visited_for_TDG_processing = True
        #     return
        # elif(conditional != None):
        #     next_tables = [conditional.true_next, conditional.false_next]
        #     if(len(next_tables)<=0):
        #         print(nodeList)
        #     for nxtNode in next_tables:
        #         newNodeList = [n for n in nodeList]
        #         self.traverseTDGRecursivelyBeforeCreatingSuperMat(nxtNode, newNodeList)
        #     conditional.is_visited_for_conditional_preprocessing = True
        #     return
        # elif(tbl != None) and (type(tbl) == SuperTable):
        #     if(tbl.is_visited_for_graph_drawing== True):
        #         return
        #     for t in tbl.subTableList:
        #         if(tbl.is_visited_for_graph_drawing== False):
        #             for a in list(t.next_tables.values()):
        #                 self.getNxGraph(a, nxGraph, nodeName, indenter = indenter+"\t")
        #             t.is_visited_for_graph_drawing= True
        #     tbl.is_visited_for_graph_drawing= True



    def getMatNodeForTDGProcessing(self, name):
        if(name==None):
            logger.info("Name is None in getNodeWithActionsForTDGProcessing. returning None")
            return None
        tbl = self.pipeline.getTblByName(name)
        conditional = self.pipeline.getConditionalByName(name)

        if(tbl != None):
            # print("Table name is "+name)
            p4TableNode =MATNode(nodeType= P4ProgramNodeType.TABLE_NODE, name = name, oriiginalP4node = tbl )
            p4TableNode.matchKey = tbl.getAllMatchFields()
            p4TableNode.actions = tbl.actions
            # p4teTableNode.actionObjectList = []
            for a in p4TableNode.actions:
                actionObject = self.getActionByName(a)
                p4TableNode.actionObjectList.append(actionObject)
            for a in list(tbl.next_tables.values()):
                nodeList = self.getNextNodeForTDG(a)
                p4TableNode.nextNodes = p4TableNode.nextNodes + nodeList
            return p4TableNode
        elif(tbl != None) and (type(tbl) == SuperTable):
            superTblNode = MATNode(nodeType= P4ProgramNodeType.SUPER_TABLE_NODE, name = name, oriiginalP4node = tbl )
            for t in tbl.subTableList:
                p4SubTableNode =MATNode(nodeType= P4ProgramNodeType.TABLE_NODE, name = name, oriiginalP4node = tbl )
                p4SubTableNode.matchKey = tbl.getAllMatchFields()
                p4SubTableNode.actions = tbl.actions
                superTblNode.matchKey = superTblNode.matchKey + p4SubTableNode.matchKey
                superTblNode.actions = superTblNode.actions  + p4SubTableNode.actions
                for tblKey in list(t.next_tables.keys()):
                    a=t.next_tables.get(tblKey)
                    nodeList = self.getNextNodeForTDG(a, self.pipelineID)
                    p4SubTableNode.nextNodes = p4SubTableNode.nextNodes + nodeList
                superTblNode.subTableMatNodes.append(p4SubTableNode)
            return superTblNode
        elif(conditional != None):
            # print("conditional name is "+name)
            p4teConditionalNode =MATNode(nodeType= P4ProgramNodeType.CONDITIONAL_NODE , name = name, oriiginalP4node = conditional)
            p4teConditionalNode.next_tables = [conditional.true_next, conditional.false_next]
            for a in p4teConditionalNode.next_tables:
                nodeList = self.getNextNodeForTDG(a)
                p4teConditionalNode.nextNodes = p4teConditionalNode.nextNodes + nodeList
            return p4teConditionalNode
        pass


    def getNextNodeForTDG(self, nodeName):
        nextNodeList = []
        for actionEntry in self.actions:
            if actionEntry.name  == nodeName:
                nextNodeList.append(nodeName)
        for tbl in self.pipeline.tables:
            if tbl.name  == nodeName:
                if(type(tbl) == Table):
                    nextNodeList.append(tbl)
                elif(type(tbl) == SuperTable):
                    nextNodeList = nextNodeList + tbl.getAllNextNodes()
        for cond in self.pipeline.conditionals:
            if cond.name  == nodeName:
                nextNodeList.append(nodeName)
        return nextNodeList














