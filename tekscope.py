#!/usr/bin/python

# tds-2024.py
# Python interface to the TDS20xx Tektronix oscilloscope
#
# Les Schaffer  Designspring, Inc.   http://designspring.com
#
# Licensed under the GPL version 2 or later; see the file LICENSE
# included with this distribution.
#
# Current status:
# Version 0.1 -- 6/7 Feb 2015 first version, uses serial interface, will do USB and GPIB later.
#                starting with TDS 2024, probably useful for many others
# Version 0.2 -- 10 Feb 2015 many improvements to code, in good working order, ready to be extended as needed. 
# Version 0.3 -- 15 Feb 2015 added a TriggerControl class, could use some ugly-code-->gorgeous-code adjustments
#                started tracking the trigger position in the plots. 
#                Adding a HORizontal control. CH, DAT, and DIS to follow
#
#
# adapated from : http://www.febo.com/geekworks/data-capture/tds-2012.html cf. https://gist.github.com/pklaus/320584 
# i think the previous line handles my responsibilities under GPL. am newcomer to licensing, please let me know if
# otherwise
#
# see also: https://github.com/python-ivi


import datetime
from math import log10, ceil
from string import split, upper
from time import sleep
from struct import unpack
from serial import Serial   # we don't need no steenkin' VISA
from numpy import array

from plotter import ScopeDisplay

# how long to sleep after issuing a write
sleeptime = 0.01

mNAN = 9.9e+37  # Tektronix "not a number"

class Measurement(object):
    """
    Given a list of measurement requests on a channel, and a function for obtaining them, acquire the measurements when call()ed and 
    set appropriate attributes to store these values. Also store appropriate stringified versions, for later display.

    Acquired measurements can be retrieved by attribute, or can be returned as a list or a dictionary.

    possible measurements:
    MEASUrement:IMMed:TYPe { FREQuency | MEAN | PERIod |PHAse | PK2pk | CRMs | MINImum | MAXImum | RISe | FALL | PWIdth | NWIdth }

    TODO:
    1. do we want immediate measurements or regular?
    2. get the associated unit, for display (why bother, here they are:)
    """
    mtypeT = ('FREQ', 'MEAN', 'PERI', 'PHAS', 'PK2P', 'CRMS', 'MINI', 'MAXI', 'RISE', 'FALL', 'PWID', 'NWID')
    munitsT = ('Hz',   'V ',    's ',    '',   'V ',   'V ',    'V ',   'V ',   's ',  's ',    's ',  's ')
    mtypeD = {meas: unit for meas, unit in zip(mtypeT, munitsT)}
    sufD = {0:' ', 3:'m', 6:'u', 9:'n', 12:'p', -3: 'k', -6:'M'}
    
    def __init__(self, mreader):
        self._immed=mreader
        self.isReset=False
        self.measL=()
        self.reset()

    def getMeasStrLD(self):
        return {m: getattr(self, m.lower()+'Str') for m in self.measL}        
    def getMeasStrLL(self):
        return [getattr(self, m.lower()+'Str') for m in self.measL]

    def __call__(self, keyL):
        # this acquires the actual reading
        # we are not doiing the units, for now
        self.reset() # might not want to reset if we have new vals!!!
        self.measL = tuple( map(upper, keyL) )
        for key in self.measL:
            if key not in self.mtypeT:
                raise ValueError('Channel does not support %s IMMed TYPe'%key)
        
            val = self._immed(key)
            
            # we make nice strings for later retrieval
            # means data is acquired throu call() and retrived via attribute
            attrN = key.lower()+'Str'
            setattr(self, attrN, self.val_to_string(val, key))

            # store raw as attr
            setattr(self, key.lower(), val)
            
        self.isReset=False # we have readings

    def val_to_string(self, val, meas):
        tmpl = '{:4s}: {:> 8.3f} '
        if val == 0.0: 
            return tmpl.format(meas, val) + ' ' + self.mtypeD[meas]
        aval = abs(val)
        
        if aval > 10.0e9: return '%4s:  ** ? **   '%meas

        if aval<1.0 or aval>=1000.:
            mulmod =3 * ceil( log10(1.0/aval)  / 3)
            scaled = val*10**mulmod
            suf = self.sufD[mulmod]
        else:
            scaled = val
            suf=' '
            
        return tmpl.format(meas,scaled) + suf + self.mtypeD[meas]

    def reset(self):
        # clear the previous readings.
        if not self.isReset:
            # reset all values
            for typ in self.mtypeT:
                setattr(self, typ.lower(), mNAN)
                setattr(self, typ.lower()+'_Str', '********')            
        self.isReset=True

def _strip(strBuf):
    return strBuf.replace('"', '')

class Channel(object):
    wfmFuncD = {'BYT_NR':int,
                'BIT_NR': int,
                'ENCDG': None,  # ASC | BIN
                'BN_FMT': None,
                'BYT_OR': None,
                'NR_PT': int,
                'WFID': _strip, # "Ch3, DC coupling, 1.0E0 V/div, 1.0E-1 s/div, 2500 points, Sample mode"
                'PT_FMT': None,
                'XINCR': float, # 4.0E-4
                'PT_OFF': int, # 0
                'XZERO': float, # -1.0E-1
                'XUNIT': _strip, # "s"
                'YMULT': float, # 4.0E-2
                'YZERO': float, # 0.0E0
                'YOFF': float, # -4.5E1
                'YUNIT': _strip #"Volts"
            }
    wfmT = wfmFuncD.keys()

    # :WFMPRE:BYT_NR 1;BIT_NR 8;ENCDG BIN;BN_FMT RI;BYT_OR LSB;NR_PT
    # 2500;WFID "Ch3, DC coupling, 5.0E-1 V/div, 1.0E-1 s/div, 2500
    # points, Sample mode";PT_FMT Y;XINCR 4.0E-4;PT_OFF 0;XZERO
    # -1.0E-1;XUNIT "s";YMULT 2.0E-2;YZERO 0.0E0;YOFF -1.69E2;YUNIT
    # "Volts"

    
    def __init__(self, chN, instr):
        self._channel = 'CH%1d'%chN
        self._instr = instr
        self._msmnt = Measurement(self.getImmed)
        self.wfmD = {}

    def getVerticalSetting(self):
        # get instrument settings
        voltsdiv=self._instr.query_float('%3s:scale?'%self._channel)
        
        if voltsdiv >= 1:
            volt_string = '%i\nV/DIV' % (voltsdiv)
        else:
            volt_string = '%i\nmV/DIV' % (voltsdiv * 1000)
        self.voltStr = volt_string
        self.voltsdiv = voltsdiv

    def getImmed(self, typ):
        self._instr.cmd('measu:imm:typ %s;:measu:imm:sou %3s'%(typ,self._channel))
        return self._instr.query_float('measu:imm:val?')

    def acqMeas(self, mL):
        # acquire some measurements, available later as self.getMeasurements()
        self._msmnt(mL)

    def getMeasStrD(self):
        return self._msmnt.getMeasStrLD()
    def getMeasStrL(self):
        return self._msmnt.getMeasStrLL()

    def wfmpreQ(self):
        tmp=self._instr.query('wfmpre?')[0:-1] # strip CR
        # strip header :WFMPRE:
        preamble = split(tmp[8:],';')
        for resp in preamble:
            name, val = resp.split(' ',1)
            if name in self.wfmT:
                func = self.wfmFuncD[name]
                if func:
                    self.wfmD[name]= func(val)
                else:
                    self.wfmD[name] = val

        # number of points in trace
        self.points = self.wfmD['NR_PT']
        if self._instr._debug: print self.wfmD

    def acquire(self, prepare):
        # for ASCII read, use 'self.read(16384)' instead of the above, and 
        # delete the next two lines.  You'll need to use 'split' to convert the 
        # comma-delimited values returned in 'tmp' to a list of values called
        # 'tmplist', and you may need to adjust the offsets used in the 'for' loop 
        # to end up with the proper number of points

        self._instr.cmd('DATA:SOURCE %3s'%self._channel)
        if prepare: self.wfmpreQ()

        tmp = self._instr.query('curv?', nBytes=9)
        # header: :CURVE #42500
        numChr = int(tmp[8])  # 4
        tmp=self._instr.read(numChr)
        points = int(tmp)
        if self._instr._debug: print 'Acquiring %d points'%points
        tmp=self._instr.read(self.wfmD['BYT_NR']*points+1) #newline at end???

        formatstring = '%ib' % (len(tmp))   # does this assume BYT_NR==1???
        tmplist = unpack(formatstring,tmp)[:-1] # there's a newline at the end of the data, thus the strange slice
        
        yoff = self.wfmD['YOFF']
        ymult = self.wfmD['YMULT']
        yzero = self.wfmD['YZERO']
        points = self.wfmD['NR_PT']
        tmp = array( map(int, tmplist) )
        self.trace =  (tmp - yoff) * ymult + yzero
        self.trace_undisplaced = tmp*ymult/self.voltsdiv
            
        if self._instr._debug: print self.trace

class HorizontalControl(object):
    horFuncD = { 'HOR:VIEW': None,
                 'HOR:MAIN:POS': float,
                 'HOR:MAIN:SCA': float
                }
    horT = horFuncD.keys()
                
    def __init__(self, instr):
        self._instr = instr
        self._horD = {}

    def __getitem__(self, key): # upwards
        val= self._instr.query_val(key)
        func = self.horFuncD[val]
        if func:
            val = func(val)
        return val

    def __setitem__(self, key, val): # downwards
        if not val: return 
        if key not in self.horT: raise ValueError('%s not in trigger dictionary'%key)
        self._instr.cmd('%s %s'%(key, val)) # in instrument

class TriggerControl(object):
    trigFuncD = {'STATE': None, # No MAIN: prepended, shrug
                 'MODE': None,
                 'TYPE': None,
                 'LEVEL': float,
                 'HOLDO': float,
                 'EDGE:SOU': None,
                 'EDGE:COUP': None,
                 'EDGE:SLO': None,
                 'PULS:SOU': None ,
                 'PULS:WIDTH:POL': None, 
                 'PULS:WIDTH:WHEN': None,
                 'PULS:WIDTH:WIDTH': float,
                 'VID:SOU': None,
                 'VID:LINE': int,
                 'VID:POL': None,
                 'VID:STAND': None,
                 'VID:SYNC': None
                }
    trigT = trigFuncD.keys()
    # no comment, must be a simpler way, have no time to figure it out!!!!!:
    mainD = {}
    edgeD = {}
    pulsD = {}
    vidD  = {}
    for key in ('MODE', 'TYPE', 'LEVEL', 'HOLDO'):
        mainD[key] = trigFuncD[key]
    for key in ('SOU', 'COUP', 'SLO'):
        edgeD[key] = trigFuncD['EDGE:%s'%key]
    for key in ('WIDTH:POL', 'WIDTH:WHEN', 'WIDTH:WIDTH', 'SOU'):
        pulsD[key] = trigFuncD['PULS:%s'%key]
    for key in ('SOU', 'LINE', 'POL', 'STAND', 'SYNC'):
        vidD[key] = trigFuncD['VID:%s'%key]

    trigTypesD={'MAIN':mainD, 'EDGE':edgeD, 'PULS':pulsD, 'VID':vidD}
                
    def __init__(self, instr):
        self._instr = instr
        self._trigD = {}

    def acqState(self):
        # first update from scope
        self._trigD['STATE'] = self._instr.query_val('TRIG:STATE?')
        return self._trigD['STATE']

    def _acqD(self, typ):
        query=self._instr.query_val
        theD = self.trigTypesD[typ]
        name = 'TRIGGER:MAIN:'
        key=''
        pref=typ
        if pref != 'MAIN':
            name=name + pref + ':'
            key=pref+':'
        for s, func in theD.items():
            val = query(name+'%s?'%s)
            if func:
                val = func(val)
            self._trigD[key+s]=val

    def _setD(self, typ, kwD):
        query=self._instr.cmd
        setT = self.trigTypesD[typ].keys()
        name = '%s:'%typ
        for key, val in kwD.items():
            if key not in setT: raise IndexError('%s not in (%s)'%(key,setT))
            self[name+key] = val
            
    def setTrigger(self, level, mode, holdo, typ, trigD):
        self['LEVEL'] = level
        self['MODE'] = mode
        self['HOLDO'] = holdo
        if typ: 
            if typ not in self.trigTypesD.keys(): raise TypeError('%s is not a trigger type'%typ)
            self._setD(typ, trigD)
            self['TYPE'] = typ

    def getTrigger(self, forceAcq = False):
        if forceAcq: self.acqSettings()
        # get the type of trigger:
        trigD = {key: self[key] for key in ('LEVEL', 'HOLDO', 'MODE', 'TYPE', 'STATE') }
        typ =  trigD['TYPE'] 
        for key in self.trigTypesD[typ].keys():
            trigD[key]= self[typ+':'+ key]
        return trigD

    def acqSettings(self):
        self.acqState()
        self._acqD('MAIN')
        self._acqD(self._trigD['TYPE'])

    def __getitem__(self, key): # upwards
        return self._trigD[key]

    def __setitem__(self, key, val): # downwards
        if not val: return 
        if key not in self.trigT: raise ValueError('%s not in trigger dictionary'%key)
        self._instr.cmd('TRIGGER:MAIN:%s %s'%(key, val)) # in instrument
        # now store local
        self._trigD[key]=val

class TektronixScope(object):
    """
    TODO ideas:
    1. could have a channels class, and add four to this device
    2. channels could have a set of measurements and a unique trace
    3. could handle various kinds of trigger and setup condx to satisfy grabbing data
    4. could autostore data (tables best for this)
    """
    
    def __init__(self, port=None, debug=False):
        self._port = port
        self._debug = debug
        self.connect()
        self.clear()
        self.identify()
        self._channelL=[]
        self._channelAcqL=[]
        for i in (1,2,3,4):
            self._channelL.append( Channel(i,self) )
        self._triggerCtl = TriggerControl(self)
        self._horCtl = HorizontalControl(self)

    def identify(self):
        sleep(sleeptime)
        self.write('*IDN?\n')
        sleep(sleeptime)
        resp=self.readline()
        if resp == self._idStr:
            print resp
        else:
            raise ValueError('Failed to get instrument id (%s)'%resp)

    def getChannel(self, chN):
        return self._channelL[chN-1]
    def channelWasAcq(self, chN):
        return chN in self._chanAcqL
    def getacqTag(self):
        return self._acqtag

    def setTrigger(self, level, mode, holdo, typ, trigD ):
        self._triggerCtl.setTrigger(level, mode, holdo, typ, trigD )

    def getTrigger(self, forceAcq):
        return self._triggerCtl.getTrigger(forceAcq)

    def query(self, req, nBytes=None):
        if self._debug:
            print "send to Serial: ", req
        self.write(req+'\n')
        sleep(sleeptime)
        if nBytes:
            resp=self.read(nBytes)
        else:
            resp=self.readline()
        if self._debug:
            print "got from Serial: ", resp,
        return resp  # for dog's sake, remove the CR once and for all

    def query_val(self, req):
        resp = self.query(req)
        return resp.strip().split()[-1]

    def query_float(self, req):
        resp = self.query(req)
        resp=float( resp.split()[1] )
        if self._debug: print 'query_float:%s'%resp
        return resp

    def cmd(self, cmdS):
        if self._debug:
            print "send to Serial: ", cmdS
        self.write(cmdS+'\n')
        sleep(sleeptime)

    def prepare(self):
        self.cmd('acquire:state on')
        raw_input('Press ENTER when ready to acquire triggered data: ')

    def complete(self):
        self.cmd('acquire:state off')

    # should catch SIGINT/SIGKILL and call __del__ and clean up buffers
    __del__ = complete

    def acquire(self, chmD, prepChannels=True):
        self._triggerCtl.acqSettings()
        self.prepare()
        self.getSweepSetting()
        self._chanAcqL=chmD.keys()
        for ch,m in chmD.items():
            chan = self.getChannel(ch)
            chan.getVerticalSetting()
            chan.acqMeas(m)
            chan.acquire(prepChannels)
        self.complete()

    def load(self):
        pass

    def dump(self):
        dfp = open('scope.dat', 'w')
        dfp.close()
        
    def getSweepSetting(self):
        sufD = {3:'m', 6:'u', 9:'n'}
        scaled=self.query_float('hor:mai:sca?')
        if scaled >= 1:
            suf = ' s'
        if scaled < 1:
            mulmod =3 * ceil( log10(1.0/scaled)  / 3)            
            scaled = scaled*10**mulmod
            suf = sufD[mulmod]+'s'
        sweepStr= '%.f' % scaled
        self.sweepStr = sweepStr + '\n' + (suf) + "/DIV"
        self.sweep=scaled

    def showFileSystem(self):
        print self.query('FILES:DIR?')
    
        
class TDS2024(TektronixScope):
    _idStr = 'TEKTRONIX,TDS 2024,0,CF:91.1CT FV:v4.12 TDS2CM:CMV:v1.04\n'

    def __init__(self, port='/dev/ttyS0', **kwD):
        super(TDS2024, self).__init__(port, kwD)

    def connect(self):
        self.serial = Serial(self._port, 9600, timeout=None)
        self.read = self.serial.read
        self.readline = self.serial.readline
        self.write = self.serial.write

    def clear(self):
        cnt=10
        while 1:
            self.serial.sendBreak() # doesnt seem to handle if other stuff in the queue
            sleep(sleeptime)
            resp=self.readline()
            if resp == 'DCL\0\n':   #  should see: [68, 67, 76, 0, 10]
                # we may have another DCL in the queue because we've repeated
                if cnt==9:
                    resp=self.readline()
                    self.serial.flushInput()
                    self.serial.flushOutput()
                if self._debug: print map(ord,resp)
                print 
                break
            if self._debug:
                print 'X',
                print map(ord, resp)
            cnt=cnt-1
            if cnt==0:  raise ValueError('Serial port did not return DCL! (%s)'%resp )


if __name__ == '__main__':
    TimeStamp =   datetime.datetime.now().isoformat().replace(':', '-').split('.')[0]
    tds2024 = TDS2024(debug=True)
    if 0:
        from pickle import dump, load
        # can't pickle the instance. have to try grabbing only attributed ....
        acqD =  {3:('FALL', 'RISE', 'PK2P', 'MAXI'), 2: ('FALL', 'RISE', 'MAXI'), 1: ('FALL', 'RISE', 'MAXI') }
        tds2024.acquire(acqD )
        tds2024.dump()

    if 1:
        mT = ('FALL', 'RISE', 'PK2P', 'CRMS')
        tds2024.setTrigger(level=4.56, holdo=None, mode='NORMAL', typ='EDGE', trigD={'SOU':'CH3'})
        print tds2024.getTrigger(forceAcq=True)
        acqD =  {3:mT, 2: mT, 1: mT}
        tds2024.acquire(acqD )
        pl=ScopeDisplay(tds2024, idStr=TimeStamp)
        pl.plotChannel(3)
        pl.plotChannel(2, scopeView=False)
        pl.plotChannel(1, scopeView=False)    
        pl.plotAll()
        pl.annotate_plots( )
        pl.show()
    if 0:  # options please!!!!
        tds2024.showFileSystem()
