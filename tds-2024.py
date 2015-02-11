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
#
#
# adapated from : http://www.febo.com/geekworks/data-capture/tds-2012.html cf. https://gist.github.com/pklaus/320584 
# i think the previous line handles my responsibilities under GPL. am newcomer to licensing, please let me know if
# otherwise
#
# see also: https://github.com/python-ivi


import datetime
from matplotlib import rc, use
rc('text', usetex=False)
rc('font', family='monospace')  # LOOKs like a scope  ;-)
# WXAgg: problems with draw below() .... use ginput() ???
# GtkAgg: /usr/lib/python2.7/dist-packages/matplotlib/backends/backend_gtk.py:253: Warning: Source ID 5 was not found when attempting to remove it
#  gobject.source_remove(self._idle_event_id)
use("TkAgg")

from matplotlib.pyplot import plot, axis, xlabel, ylabel, gca, grid, text, show, figure, xticks, title, rcParams, savefig
rcParams['savefig.directory'] = None  # use default
from numpy import array, arange
from math import log10, ceil
from string import split, upper
from time import sleep
from struct import unpack
from serial import Serial   # we don't need no steenkin' VISA

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

class TDS2024(Serial):
    """
    TODO ideas:
    1. could have a channels class, and add four to this device
    2. channels could have a set of measurements and a unique trace
    3. could handle various kinds of trigger and setup condx to satisfy grabbing data
    4. could autostore data (tables best for this)
    """
    _idStr = 'TEKTRONIX,TDS 2024,0,CF:91.1CT FV:v4.12 TDS2CM:CMV:v1.04\n'
    
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

        self._channelL=[]
        self._channelAcqL=[]
        for i in (1,2,3,4):
            self._channelL.append( Channel(i,self) )

    def getChannel(self, chN):
        return self._channelL[chN-1]
    def channelWasAcq(self, chN):
        return chN in self._chanAcqL
    def getacqTag(self):
        return self._acqtag
    
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
        raw_input('Press ENTER when ready to acquire triggered data: ')

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

class TestScope(TDS2024):
    def acquire(self, chmD, prepChannels=True):
        pass

class ScopeDisplay(object):
    colorD = {1:'yellow', 2: 'aqua', 3: 'purple', 4: 'darkgreen'} # approx channel colors

    def __init__(self, instr):
        self.instr=instr
        self.figL=[]
        self.tag=None
        self.cidD={}
    def plotAll(self):
        f=figure('CHALL')
        self.figL.append(f)
        measD={}
        chNL = [ ch for ch in range(1,5)  if self.instr.channelWasAcq(ch) ]
        for chN in chNL:
            self.plotChannel(chN, scopeView=True, newfig=False, showMeas=False)
        self.displayMeasurements(chNL, addIDatTop=True)

    def displayMeasurements(self, chNL, addIDatTop=False):
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
        vdelta = 0.22* (vrange / 8)
        
        if solo:
            vbase=miny+.09*vrange
        else:
            vbase=miny-2.7*vrange/100  # should be a little lower

        notAdded=True
        for chN in chNL:
            chan = self.instr.getChannel(chN)        
            mstr = chan.getMeasStrL()

            if addIDatTop and notAdded:
                tag = chan.wfmD['WFID'].replace('%1d'%chN, '*', 1)
                title(tag, size=10)
                notAdded=False
                
            i=0
            for m in mstr:
                x,y= positioner(chN, i)
                text( x, y, m , color=self.colorD[chN], backgroundcolor='silver', size=6, family= 'monospace')  # use fixed width font???
                i=i+1

    def plotChannel(self, chN, scopeView=False, newfig=True, showMeas=True):
        # plain ole plot, single channel
        # have to figure out how to generically combine channels and measurements
        if not self.instr.channelWasAcq(chN):
            print '%s was not acquired, skipping'%chN
            return 
        labelSz=10
        chan = self.instr.getChannel(chN)

        if newfig:
            f=figure('CH%1d'%chN)
            self.figL.append(f)
            title(chan.wfmD['WFID'], size=10)
        
        points=chan.points
        x = 10.0*arange(points)/points
        trace =  chan.trace_undisplaced if scopeView else  chan.trace
        plot(x,trace, color=self.colorD[chN])

        xlabel(self.instr.sweepStr, size=labelSz)
        theaxes = gca()
        theaxes.set_xticklabels([])
        xticks( arange(0,10,1) )
        
        if scopeView:
            axis([0,10,-4,4])
            ylabel(chan.voltStr, size=labelSz)
            theaxes.set_yticklabels([])
        else:
            miny=trace.min()
            maxy=trace.max()
            vrange=maxy-miny
            miny=miny-0.1*vrange
            maxy=maxy+0.1*vrange
            vrange=maxy-miny
            axis([0,10,miny, maxy])
            ylabel(chan.wfmD['YUNIT'], size=labelSz)

        grid(1)

        if showMeas: self.displayMeasurements((chN,) )

    def onclick(self, event):
        ax = gca()
        fig = ax.get_figure()
        xmin,xmax=ax.get_xlim()
        ymin,ymax=ax.get_ylim()        
        inside = event.xdata< xmax and event.xdata> xmin and event.ydata<ymax and event.ydata>ymin
        if not inside: return 
        
        if fig in self.figL:
            self.lastTxt = text(event.xdata, event.ydata, self.tag)
            fig.canvas.draw()
            self.figL.remove(fig) # just one annotation
            # could deregister callbacks when done
            fig.canvas.mpl_disconnect(self.cidD[fig])
            self.cidD.pop(fig)
            savefig(fig.get_label()+'-'+TimeStamp+'.png')

    def annotate_plots(self):
        # add an annotation to zero or more of the plots for the current data acquisition

        for fig in self.figL:
            cid = fig.canvas.mpl_connect('button_press_event', self.onclick)
            self.cidD[fig]=cid
            fig.show()
            
        if not self.tag:
            self.tag = raw_input("Enter a tag description: ")


if __name__ == '__main__':
    TimeStamp =   datetime.datetime.now().isoformat().replace(':', '-').split('.')[0]
    tds2024 = TDS2024(debug=False)

    if 0:
        from pickle import dump, load
        # can't pickle the instance. have to try grabbing only attributed ....
        acqD =  {3:('FALL', 'RISE', 'PK2P', 'MAXI'), 2: ('FALL', 'RISE', 'MAXI'), 1: ('FALL', 'RISE', 'MAXI') }
        tds2024.acquire(acqD )
        tds2024.dump()

    if 1:
        mT = ('FALL', 'RISE', 'PK2P', 'CRMS')
        acqD =  {3:mT, 2: mT, 1: mT}
        tds2024.acquire(acqD )
        pl=ScopeDisplay(tds2024)
        pl.plotChannel(3)
        pl.plotChannel(2, scopeView=False)
        pl.plotChannel(1, scopeView=False)    
        pl.plotAll()
        pl.annotate_plots( )
        show()
    if 0:  # options please!!!!
        tds2024.showFileSystem()
    if 0:
        acqD =  {3:('PK2P', 'PERI', 'FALL', 'RISE'), 2: ('FALL', 'RISE'), 1: ('FALL', 'RISE') }
        tds2024.acquire(acqD )
        tds2024.plotAll()           
        show()
