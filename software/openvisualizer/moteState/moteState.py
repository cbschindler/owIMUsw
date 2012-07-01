
import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('moteState')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import copy
import time
import threading

from moteConnector import ParserStatus

class StateElem(object):
    
    def __init__(self):
        self.numUpdates                = 0
    
    def update(self):
        self.lastUpdated               = time.time()
        self.numUpdates               += 1
    
    def __str__(self):
        members = [attr for attr in dir(self) if not callable(attr) and not attr.startswith("__")]
        output = ["{0:>20}: {1}".format(m,getattr(self,m)) for m in members]
        return '\n'.join(output)

class StateOutputBuffer(StateElem):
    
    def update(self,notif):
        StateElem.update(self)
        self.index_write               = notif.index_write
        self.index_read                = notif.index_read

class StateAsn(StateElem):
    
    def update(self,notif):
        StateElem.update(self)
        self.asn                       = notif.asn_0_1<<12 + \
                                         notif.asn_2_3<<4  + \
                                         notif.asn_4

class StateMacStats(StateElem):
    
    def update(self,notif):
        StateElem.update(self)
        self.syncCounter               = notif.syncCounter
        self.minCorrection             = notif.minCorrection
        self.maxCorrection             = notif.maxCorrection
        self.numDeSync                 = notif.numDeSync

class StateScheduleRow(StateElem):

    def update(self,notif):
        StateElem.update(self)
        self.slotOffset                = notif.slotOffset
        self.type                      = notif.type
        self.shared                    = notif.shared
        self.channelOffset             = notif.channelOffset
        self.addrType                  = notif.addrType
        self.neighbor                  = notif.neighbor
        self.backoffExponent           = notif.backoffExponent
        self.backoff                   = notif.backoff
        self.numRx                     = notif.numRx
        self.numTx                     = notif.numTx
        self.numTxACK                  = notif.numTxACK
        self.lastUsedAsn               = notif.lastUsedAsn_0_1<<12 + \
                                         notif.lastUsedAsn_2_3<<4  + \
                                         notif.lastUsedAsn_4

class StateQueueRow(StateElem):
    
    def update(self,creator,owner):
        StateElem.update(self)
        self.creator                   = creator
        self.creator                   = owner

class StateQueue(StateElem):
    
    def __init__(self):
        StateElem.__init__(self)
        
        self.table = []
        for i in range(10):
            self.table.append(StateQueueRow())
    
    def update(self,notif):
        StateElem.update(self)
        self.table[0].update(notif.creator_0,notif.owner_0)
        self.table[1].update(notif.creator_1,notif.owner_1)
        self.table[2].update(notif.creator_2,notif.owner_2)
        self.table[3].update(notif.creator_3,notif.owner_3)
        self.table[4].update(notif.creator_4,notif.owner_4)
        self.table[5].update(notif.creator_5,notif.owner_5)
        self.table[6].update(notif.creator_6,notif.owner_6)
        self.table[7].update(notif.creator_7,notif.owner_7)
        self.table[8].update(notif.creator_8,notif.owner_8)
        self.table[9].update(notif.creator_9,notif.owner_9)

class StateNeighborsRow(StateElem):
    
    def update(self,notif):
        StateElem.update(self)
        self.used                      = notif.used
        self.parentPreference          = notif.parentPreference
        self.stableNeighbor            = notif.stableNeighbor
        self.switchStabilityCounter    = notif.switchStabilityCounter
        self.addr_64b                  = notif.addr_64b
        self.DAGrank                   = notif.DAGrank
        self.numRx                     = notif.numRx
        self.numTx                     = notif.numTx
        self.numTxACK                  = notif.numTxACK
        self.asn                       = notif.asn_0_1<<12 + \
                                         notif.asn_2_3<<4  + \
                                         notif.asn_4

class StateIsSync(StateElem):
    
    def update(self,notif):
        StateElem.update(self)
        self.isSync                    = notif.isSync

class StateIdManager(StateElem):
    
    def update(self,notif):
        StateElem.update(self)
        self.isDAGroot                 = notif.isDAGroot
        self.isBridge                  = notif.isBridge
        self.my16bID                   = notif.my16bID
        self.my64bID                   = notif.my64bID
        self.myPANID                   = notif.myPANID
        self.myPrefix                  = notif.myPrefix

class StateMyDagRank(StateElem):
    
    def update(self,notif):
        StateElem.update(self)
        self.myDAGrank                 = notif.myDAGrank

class StateTable(StateElem):

    def __init__(self,rowClass):
        StateElem.__init__(self)
        
        self.rowClass                  = rowClass
        self.table                     = []

    def update(self,notif):
        StateElem.update(self)
        while len(self.table)<notif.row+1:
            self.table.append(self.rowClass())
        self.table[notif.row].update(notif)

class moteState(object):
    
    ST_OUPUTBUFFER      = 'OutputBuffer'
    ST_ASN              = 'Asn'
    ST_MACSTATS         = 'MacStats'
    ST_SCHEDULEROW      = 'ScheduleRow'
    ST_SCHEDULE         = 'Schedule'
    ST_QUEUEROW         = 'QueueRow'
    ST_QUEUE            = 'Queue'
    ST_NEIGHBORSROW     = 'NeighborsRow'
    ST_NEIGHBORS        = 'Neighbors'
    ST_ISSYNC           = 'IsSync'
    ST_IDMANAGER        = 'IdManager'
    ST_MYDAGRANK        = 'MyDagRank'
    
    def __init__(self,moteConnector):
        
        # log
        log.debug("create instance")
        
        # store params
        self.moteConnector                  = moteConnector
        
        # local variables
        self.parserStatus                   = ParserStatus.ParserStatus()
        self.stateLock                      = threading.Lock()
        self.state                          = {}
        
        self.state[self.ST_OUPUTBUFFER]     = StateOutputBuffer()
        self.state[self.ST_ASN]             = StateAsn()
        self.state[self.ST_MACSTATS]        = StateMacStats()
        self.state[self.ST_SCHEDULE]        = StateTable(StateScheduleRow)
        self.state[self.ST_QUEUE]           = StateQueue()
        self.state[self.ST_NEIGHBORS]       = StateTable(StateNeighborsRow)
        self.state[self.ST_ISSYNC]          = StateIsSync()
        self.state[self.ST_IDMANAGER]       = StateIdManager()
        self.state[self.ST_MYDAGRANK]       = StateMyDagRank()
        
        self.notifHandlers = {
                self.parserStatus.named_tuple[self.ST_OUPUTBUFFER]:
                    self.state[self.ST_OUPUTBUFFER].update,
                self.parserStatus.named_tuple[self.ST_ASN]:
                    self.state[self.ST_ASN].update,
                self.parserStatus.named_tuple[self.ST_MACSTATS]:
                    self.state[self.ST_MACSTATS].update,
                self.parserStatus.named_tuple[self.ST_SCHEDULEROW]:
                    self.state[self.ST_SCHEDULE].update,
                self.parserStatus.named_tuple[self.ST_QUEUEROW]:
                    self.state[self.ST_QUEUE].update,
                self.parserStatus.named_tuple[self.ST_NEIGHBORSROW]:
                    self.state[self.ST_NEIGHBORS].update,
                self.parserStatus.named_tuple[self.ST_ISSYNC]:
                    self.state[self.ST_ISSYNC].update,
                self.parserStatus.named_tuple[self.ST_IDMANAGER]:
                    self.state[self.ST_IDMANAGER].update,
                self.parserStatus.named_tuple[self.ST_MYDAGRANK]:
                    self.state[self.ST_MYDAGRANK].update,
            }
        
        # register with moteConnector
        self.moteConnector.register([self.moteConnector.TYPE_STATUS],
                                    self.receivedData_notif)
    
    #======================== public ==========================================
    
    def receivedData_notif(self,notif):
        
        # log
        log.debug("received {0}".format(notif))
        
        # lock the state data
        self.stateLock.acquire()
        
        # call handler
        found = False
        for k,v in self.notifHandlers.items():
            if self._isnamedtupleinstance(notif,k):
                found = True
                v(notif)
                break
        
        # unlock the state data
        self.stateLock.release()
        
        if found==False:
            raise SystemError("No handler for notif {0}".format(notif))
    
    def getStateElem(self,elemName):
        
        if elemName not in self.state:
            raise ValueError('No state called {0}'.format(elemName))
        
        self.stateLock.acquire()
        returnVal = copy.deepcopy(self.state[elemName])
        self.stateLock.release()
        
        return returnVal
    
    def getStateElemNames(self):
        
        self.stateLock.acquire()
        returnVal = self.state.keys()
        self.stateLock.release()
        
        return returnVal
    
    #======================== private =========================================
    
    def _isnamedtupleinstance(self,var,tupleInstance):
        return var._fields==tupleInstance._fields