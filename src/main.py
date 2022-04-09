from DependencyAnlyzer.P4ProgramGraph import P4ProgramGraph
from P4ProgramParser.P416JsonParser import ParsedP416ProgramForV1ModelArchitecture
from P4ProgramParser.P4ProgramParserFactory import P4ProgramParserFactory
from ParserMapper.make_tcam import buildParserMapper
from RMTHardwareSimulator import RMTHardwareFactory
from util import loadP416JsonUsingAutoGeneratedJsonParser
from ParserMapper import HeaderLib
from ParserMapper import *
from ParserMapper import RefCount
from P416JsonParser import  ParserOpOp
from utils import Util

#64, 96, and 64 words of 8, 16, and 32b
p4ProgramParserFactory = P4ProgramParserFactory()
hw = RMTHardwareFactory.createRmtHardware(rmtHardwaRemodelName = "RMT_V1",
    instructionSetConfigurationJsonFile= "../Resources/HardwareConfigs/RMTV1ModelInstructions.json",
    hardwareSpecConfigurationJsonFile = "../Resources/HardwareConfigs/RMTV1model32Stages.json")
# p4program = p4ProgramParserFactory.getParsedP4Program(p4JsonFile="../Resources/P4ProgramsForPaper/PacketCounter/qos_modifier.json",p4VersionAndArchitecture="P416_V1_Model")
p4program = p4ProgramParserFactory.getParsedP4Program(p4JsonFile="../Resources/P4ProgramsForPaper/L2L3Simple/l2l3Simple.json",p4VersionAndArchitecture="P416_V1_Model")
# p4program = p4ProgramParserFactory.getParsedP4Program(p4JsonFile="../Resources/P4ProgramsForPaper/L2L3Complex/l2l3complex.json",p4VersionAndArchitecture="P416_V1_Model")
# p4program = p4ProgramParserFactory.getParsedP4Program(p4JsonFile="../Resources/P4ProgramsForPaper/P4anony/p4anony.json",p4VersionAndArchitecture="P416_V1_Model")


p4program.buildHeaderVector(hw)
p4ProgramGraph = P4ProgramGraph(p4program)

headerFieldSpecsInP4ProgramToBeUsedForParserMapper, totalRawBitwidth = p4ProgramGraph.headeranalyzer(hw)
parseGraphHeaderList, parsedGraphHeaders, initHeader = HeaderLib.loadParseGraph(parserObject = p4program.parsers[0], p4ProgramGraph = p4ProgramGraph) # There is only one parser in v1model
buildParserMapper(parseGraphHeaderList, parsedGraphHeaders, hw, initHeader)

p4ProgramGraph.loadPipelines(hw)
headerFieldSpecsInP4Program,totalRawBitwidth = p4ProgramGraph.headeranalyzer(hw)
# mappedPacketHeaderVector1 = hw.mapHeaderFieldsUsingGoogleOR(headerFieldSpecsInP4Program)
# headerFieldSpecsInP4Program = {33: 1, 16: 1} # this line is for test purpose
mappedPacketHeaderVector = hw.mapHeaderFields(headerFieldSpecsInP4Program)
print(mappedPacketHeaderVector)
p4ProgramGraph.storePHVFieldMappingForHeaderFields(mappedPacketHeaderVector=mappedPacketHeaderVector)
Util.calculatePHVWaste(headerFieldSpecsInP4Program, mappedPacketHeaderVector,totalRawBitwidth)
p4ProgramGraph.embedPipelines(hw)
hw.calculateTotalLatency(p4ProgramGraph, hw)



#===================== Upto here header mappign is done



