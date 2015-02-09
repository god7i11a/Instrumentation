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
#
#
# adapated from : http://www.febo.com/geekworks/data-capture/tds-2012.html cf. https://gist.github.com/pklaus/320584 
# i think the previous line handles my responsibilities under GPL. am newcomer to licensing, please let me know if
# otherwise
#
# see also: https://github.com/python-ivi



from matplotlib.pyplot import plot, axis, xlabel, ylabel, gca, grid, text, show, figure, xticks
from numpy import array, arange
from string import split, upper
from time import sleep
from struct import unpack
from serial import Serial   # we don't need no steenkin' VISA 

# how long to sleep after issuing a write
sleeptime = 0.01

mNAN = 9.9e+37  # Tektronic "not a number"

class Measurement(object):
    """
     Given a list of measurement requests on a channel, and a function for obtaining them, acquire the measurements when call()ed and 
     set appropriate attributes to store these values. Also store appropriate stringified versions, for later display.

    Acquired measurements can be retrieved by attribute, or can be returned as a list or a dictionary.

    possible measurements:
    MEASUrement:IMMed:TYPe { FREQuency | MEAN | PERIod |PHAse | PK2pk | CRMs | MINImum | MAXImum | RISe | FALL | PWIdth | NWIdth }

    TODO:
    1. do we want immediate measurements or regular?
    2. get the associated unit, for display
    """
    mtypeT = ('FREQ', 'MEAN', 'PERI', 'PHA', 'PK2', 'CRM', 'MINI', 'MAXI', 'RIS', 'FALL', 'PWI', 'NWI')
    isReset=False
    
    def __init__(self, mreader):
        self._immed=mreader
        self.reset()
        self.measL=()

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
            # dropcase
            key = key.lower()
            # store raw as attr
            setattr(self, key, val)
            
            # we make nice strings for later retrieval
            # means data is acquired throu call() and retrived via attribute
            attrN = '_'+key+'Str'
            func = getattr(self, attrN)
            func(val)
        self.isReset=False # we have readings

    # these convenience funcs could really be classified according to the UNIT of the measurement.
    # so Volts, seconds, and Hz. 
    def _pk2Str(self, val):
        if val != mNAN:
            peak_string = 'PK2p: %.3f V' % (val)
        else: peak_string = 'PK2p: ***'
        self.pk2Str = peak_string
    def _maxiStr(self, val):
        if val != mNAN:
            maxi_string = 'MAXI: %.3f V' % (val)
        else: maxi_string = 'MAXI: ***'
        self.maxiStr = maxi_string
    def _meanStr(self, val):
        if val != mNAN:
            mean_string = 'MEAN: %.3f V' % (val)
        else: mean_string = 'MEAN: ***'
        self.meanStr = mean_string
    def _periStr(self, val):
        if val >= 1:
            period_val = val
            period_suf = "S"
        if val < 1:
            period_val = val * 10e2
            period_suf = "mS"
            if val < 0.001:
                sweep_val = val * 10e5
                sweep_suf = "uS"
                if val < 0.000001:
                    period_val = val * 10e8
                    period_suf = "nS"
        if val != mNAN:
            period_string = 'PERI: %.3f' % (period_val) + ' ' + period_suf
        else: period_string = 'PERI: ****'
        self.periStr = period_string
    def _freqStr(self,val):
        if val < 1e3:
            freq_val = val
            freq_suf = "Hz"
        if val < 1e6:
            freq_val = val / 10e2
            freq_suf = "kHz"
        if val >= 1e6:
            freq_val = val / 10e5
            freq_suf = "MHz"
        if val != mNAN:
            freq_string = 'FREQ: %.3f' % (freq_val) + ' ' + freq_suf
        else: freq_string = 'FREQ: ***'
        self.freqStr = freq_string
    def _risStr(self,val):
        if val != mNAN:
            self.risStr = 'RISe: %.3f s'%val
        else: self.risStr = 'RISe: ***'
    def _fallStr(self,val):
        if val != mNAN:
            self.fallStr = 'FALL: %.3f s'%val
        else: self.fallStr = 'FALL: ***'

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
    wfmD = {}
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

class TDS2024(Serial):
    """
    TODO ideas:
    1. could have a channels class, and add four to this device
    2. channels could have a set of measurements and a unique trace
    3. could handle various kinds of trigger and setup condx to satisfy grabbing data
    4. could autostore data (tables best for this)
    """
    _idStr = 'TEKTRONIX,TDS 2024,0,CF:91.1CT FV:v4.12 TDS2CM:CMV:v1.04\n'
    _channelL=[]
    _channelAcqL=[]
    
    def __init__(self, port="/dev/ttyS0", debug=False):
        self._port = port
        self._debug = debug
        super(TDS2024,self ).__init__(port, 9600, timeout=None)
        self.sendBreak()
        sleep(sleeptime)
        resp=self.readline()
        if resp[0:3] != 'DCL':
            raise ValueError('Serial port did not return DCL! (%s)'%resp )
        sleep(sleeptime)
        self.write('*IDN?\n')
        sleep(sleeptime)
        resp=self.readline()
        if resp == self._idStr:
            print resp
        else:
            raise ValueError('Failed to get instrument id (%s)'%resp)

        for i in (1,2,3,4):
            self._channelL.append( Channel(i,self) )

    def getChannel(self, chN):
        return self._channelL[chN-1]
    def channelWasAcq(self, chN):
        return chN in self._chanAcqL
    
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
        return resp

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
        raw_input('Press ENTER to trigger measurement: ')

    def complete(self):
        self.cmd('acquire:state off')

    __del__ = complete

    def acquire(self, chmD, prepChannels=True):
        self.prepare()
        self.getSweepSetting()
        self._chanAcqL=chmD.keys()
        for ch,m in chmD.items():
            chan = self.getChannel(ch)
            chan.getVerticalSetting()
            chan.acqMeas(m)
            chan.acquire(prepChannels)
        self.complete()
        
    def getSweepSetting(self):
        tmp=self.query_float('hor:mai:sca?')
        tmp = float(tmp)
        rawsweep = tmp
        if tmp >= 1:
            sweep_val = tmp
            sweep_suf = "S"
        if tmp < 1:
            sweep_val = tmp * 10e2
            sweep_suf = "mS"
            if tmp < 0.001:
                sweep_val = tmp * 10e5
                sweep_suf = "uS"
                if tmp < 0.000001:
                    sweep_val = tmp * 10e8
                    sweep_suf = "nS"
        sweep_val = '%.f' % sweep_val
        self.sweepStr = sweep_val + '\n' + (sweep_suf) + "/DIV"

    def showFileSystem(self):
        print self.query('FILES:DIR?')

    colorD = {1:'yellow', 2: 'aqua', 3: 'purple', 4: 'darkgreen'} # approx channel colors

    def plotAll(self):
        figure('CH: ALL')
        measD={}
        chNL = [ ch for ch in range(1,5)  if self.channelWasAcq(ch) ]
        for chN in chNL:
            self.plotChannel(chN, scopeView=True, newfig=False, showMeas=False)
        self.displayMeasurements(chNL)

    def displayMeasurements(self, chNL ):
        """
            # the limits are always 0 to 10 and -4 to 4 for this scope (make class vars for it then!
            posL = ( (0.03*10,-3.4),  # can add more as needed, algorithmically if i think hard enuf!
                    (0.03*10,-3.9),
                    (0.72*10,-3.4),
                    (0.72*10,-3.9)
                    )
            posL = ( (0.03*10,-4.3),  # can add more as needed, algorithmically if i think hard enuf!
                    (0.03*10,-4.5),
                    (0.72*10,-4.3),
                    (0.72*10,-4.5)
                    )
            posL = ( (0.03*10,miny+high*vrange),  # can add more as needed, algorithmically if i think hard enuf!
                    (0.03*10,miny+low*vrange) ,
                    (0.72*10,miny+high*vrange),
                    (0.72*10,miny+low*vrange)
                    )
        """
        def positioner(chN, i):
            if solo:
                if i<2:
                    x = 0.1*hrange+hdelta
                    y=vbase-i*vdelta
                else:
                    x =  0.8*hrange + hdelta
                    y=vbase-(i-2)*vdelta
            else:
                y = vbase-i*vdelta
                if chN<3:
                    x = (chN-1)*2*hrange/10+3*hdelta
                else:
                    x = (chN)*2*hrange/10+3*hdelta
            return x,y

        solo = len(chNL)==1
        
        ax = gca()
        miny, maxy = ax.get_ylim()
        minx, maxx = ax.get_xlim()
        vrange=maxy-miny
        hrange=maxx-minx
        hdelta = 3*hrange/1000
        vdelta = 0.2* (vrange / 8)
        
        if solo:
            vbase=miny+.09*vrange
        else:
            vbase=miny-2.5*vrange/100  # should be a little lower

        for chN in chNL:
            chan = self.getChannel(chN)        
            mstr = chan.getMeasStrL()

            i=0
            for m in mstr:
                x,y= positioner(chN, i)
                text( x, y, m , color=self.colorD[chN], backgroundcolor='silver', size='x-small')  # use fixed width font???
                i=i+1

    def plotChannel(self, chN, scopeView=False, newfig=True, showMeas=True):
        # plain ole plot, single channel
        # have to figure out how to generically combine channels and measurements
        if not self.channelWasAcq(chN):
            print '%s was not acquired, skipping'%chN
            return 

        if newfig: figure('CH%1d'%chN)
        chan = self.getChannel(chN)
        
        points=chan.points
        x = 10.0*arange(points)/points
        trace =  chan.trace_undisplaced if scopeView else  chan.trace
        plot(x,trace, color=self.colorD[chN])

        xlabel(self.sweepStr)
        theaxes = gca()
        theaxes.set_xticklabels([])
        xticks( arange(0,10,1) )
        
        if scopeView:
            axis([0,10,-4,4])
            ylabel(chan.voltStr)
            theaxes.set_yticklabels([])
        else:
            miny=trace.min()
            maxy=trace.max()
            vrange=maxy-miny
            miny=miny-0.1*vrange
            maxy=maxy+0.1*vrange
            vrange=maxy-miny
            axis([0,10,miny, maxy])
            ylabel(chan.wfmD['YUNIT'])

        grid(1)

        if showMeas: self.displayMeasurements((chN,) )
                                     
if __name__ == '__main__':
    tds2024 = TDS2024(debug=True)

    if 1:
        acqD =  {3:('FALL', 'RIS', 'PK2', 'MAXI'), 2: ('FALL', 'RIS', 'MAXI'), 1: ('FALL', 'RIS', 'MAXI') }
        tds2024.acquire(acqD )
        tds2024.plotChannel(3)
        tds2024.plotChannel(2, scopeView=True)
        tds2024.plotChannel(1, scopeView=True)    
        tds2024.plotAll()   
        show()
    if 0:  # options please!!!!
        tds2024.showFileSystem()
    if 0:
        acqD =  {3:('PK2', 'PERI', 'FALL', 'RIS'), 2: ('FALL', 'RIS'), 1: ('FALL', 'RIS') }
        tds2024.acquire(acqD )
        tds2024.plotAll()           
        show()
