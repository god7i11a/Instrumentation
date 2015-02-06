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
# Version 0.1 -- 6 Feb 2015 first version, uses serial interface, will do USB and GPIB later.
#                starting with TDS 2024, probably useful for many others
#
#
# adapated from : http://www.febo.com/geekworks/data-capture/tds-2012.html cf. https://gist.github.com/pklaus/320584 
# i think the previous line handles my responsibilities under GPL. am newcomer to licensing, please let me know if
# otherwise



from matplotlib.pylab import *
from numpy import array
from string import *
from time import *
from struct import *
from serial import Serial   # we don't need no steenkin' VISA 

# how long to sleep after issuing a write
sleeptime = 0.1

class TDS2024(Serial):
    idStr = 'TEKTRONIX,TDS 2024,0,CF:91.1CT FV:v4.12 TDS2CM:CMV:v1.04\n'
    wfmD = {}
    _wfmD = {'BYT_NR':int,
            'UNIT': None,
            'BYT_NR': int,
            'BIT_NR': int,
            'ENCDG': None,  # ASC | BIN
            'BN_FMT': None,
            'BYT_OR': None,
            'NR_PT': int,
            'WFID': None, # "Ch3, DC coupling, 1.0E0 V/div, 1.0E-1 s/div, 2500 points, Sample mode"
            'PT_FMT': None,
            'XINCR': float, # 4.0E-4
            'PT_OFF': int, # 0
            'XZERO': float, # -1.0E-1
            'XUNIT': None, # "s"
            'YMULT': float, # 4.0E-2
            'YZERO': float, # 0.0E0
            'YOFF': float, # -4.5E1
            'YUNIT': None #"Volts"
            }
    _wfmT = _wfmD.keys()
    
    def __init__(self, port="/dev/ttyS0", debug=False):
        self._port = port
        self._debug = debug
        super(TDS2024,self ).__init__(port, 9600, timeout=None)
        self.sendBreak()
        resp=self.readline()
        if resp[0:3] != 'DCL':
            raise ValueError('Serial port did not return DCL! (%s)'%resp )
        sleep(sleeptime)
        self.write('*IDN?\n')
        sleep(sleeptime)
        while 1:
            resp=self.readline()
            if resp == self.idStr:
                print resp
                break

        self._channel=None

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

    def setChannel(self, ch='CH3'):
        if ch != self._channel:
            self.cmd('DATA:SOURCE %3s'%ch)
            self.wfmpreQ()
            self._channel=ch

    def wfmpreQ(self):
        tmp=self.query('wfmpre?')
        # strip header :WFMPRE:
        preamble = split(tmp[8:],';')
        for resp in preamble:
            name, val = resp.split(' ',1)
            if name in self._wfmT:
                func = self._wfmD[name]
                if func:
                    self.wfmD[name]= func(val)
                else:
                    self.wfmD[name] = val
        print self.wfmD
        # number of points in trace
        self.points = self.wfmD['NR_PT']
        # volts per bit (-127 to +128)
        voltsbit = self.wfmD['YUNIT']
        if self._debug: print  self.wfmD['NR_PT'], self.wfmD['YUNIT']

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
        self.sweepStr = sweep_val + ' ' + (sweep_suf) + " / div"

    def getVerticalSetting(self):
        ch = self._channel
        # get instrument settings
        voltsdiv=self.query_float('%3s:scale?'%ch)
        
        if voltsdiv >= 1:
            volt_string = '%i V / div' % (voltsdiv)
        else:
            volt_string = '%i mv / div' % (voltsdiv * 1000)
        self.voltStr = volt_string
        self.voltsdiv = voltsdiv
        

    def getMeasurements(self):
        ch = self._channel        
        # get some measurements, just for fun
        tmp = 9.9E37
        self.cmd('measu:imm:typ PK2;:measu:imm:sou %3s'%ch)
        tmp=self.query_float('measu:imm:val?')
        if tmp != 9.9E37:
            peak_string = 'Pk-Pk: %.3f V' % (tmp)
        else: peak_string = ''
        self.peakStr = peak_string
        
        self.cmd('measu:imm:typ MEAN;:measu:imm:sou %3s'%ch)
        tmp=self.query_float('measu:imm:val?')
        if tmp != 9.9E37:
            mean_string = 'Mean: %.3f V' % (tmp)
        else: mean_string = ''
        self.meanStr = mean_string
        
        self.cmd('measu:imm:typ PERI;:measu:imm:sou %3s'%ch)
        tmp=self.query_float('measu:imm:val?')
        if tmp >= 1:
            period_val = tmp
            period_suf = "S"
        if tmp < 1:
            period_val = tmp * 10e2
            period_suf = "mS"
            if tmp < 0.001:
                sweep_val = tmp * 10e5
                sweep_suf = "uS"
                if tmp < 0.000001:
                    period_val = tmp * 10e8
                    period_suf = "nS"
        if tmp != 9.9E37:
            period_string = 'Period: %.3f' % (period_val) + ' ' + period_suf
        else: period_string = ''
        self.periodStr = period_string
        
        self.cmd('measu:imm:typ FREQ;:measu:imm:sou %3s'%ch)
        tmp=self.query_float('measu:imm:val?')
        if tmp < 1e3:
            freq_val = tmp
            freq_suf = "Hz"
        if tmp < 1e6:
            freq_val = tmp / 10e2
            freq_suf = "kHz"
        if tmp >= 1e6:
            freq_val = tmp / 10e5
            freq_suf = "MHz"
        
        if tmp != 9.9E37:
            freq_string = 'Freq: %.3f' % (freq_val) + ' ' + freq_suf
        else: freq_string = ''
        self.freqStr = freq_string

    def curve(self, ch=None):
        # for ASCII read, use 'self.read(16384)' instead of the above, and 
        # delete the next two lines.  You'll need to use 'split' to convert the 
        # comma-delimited values returned in 'tmp' to a list of values called
        # 'tmplist', and you may need to adjust the offsets used in the 'for' loop 
        # to end up with the proper number of points

        if ch:  # change channels if requested
            self.setChannel(ch)
            
        tmp = self.query('curv?', nBytes=9)
        # header: :CURVE #42500
        numChr = int(tmp[8])  # 4
        tmp=self.read(numChr)
        points = int(tmp)
        if self._debug: print 'Acquiring %d points'%points
        tmp=self.read(self.wfmD['BYT_NR']*points+1) #newline at end???

        formatstring = '%ib' % (len(tmp))
        tmplist = unpack(formatstring,tmp)
        
        yoff = self.wfmD['YOFF']
        ymult = self.wfmD['YMULT']
        yzero = self.wfmD['YZERO']
        points = self.wfmD['NR_PT']
        trace = []
        # there's a newline at the end of the data, thus the strange slice
        for x in tmplist[0:-1]:
            trace.append( ( int(x) - yoff) * ymult + yzero )
        self.trace = array(trace)
        if self._debug: print trace
        self.cmd('acquire:state off')
    
    def plot_reticule(self):
        # was the original idea of predecessor, i need to think through how to do it generically
        # the idea would be to make the plot look like the scope window. wooopie!!!
        points=self.points
        voltsdiv = self.voltsdiv

        plot(self.trace)
        axis([0,points,-5*voltsdiv,5*voltsdiv])
        xlabel(self.sweepStr)
        ylabel(self.voltStr)
        theaxes = gca()
        theaxes.set_xticklabels([])
        if not theaxes.is_first_col():
            theaxes.set_yticklabels([])
        if not theaxes.is_last_row():
            theaxes.set_xticklabels([])
        grid(1)

        text(0.03*points,-4.9*voltsdiv, self.peakStr)
        text(0.03*points,-4.4*voltsdiv, self.meanStr)
        text(0.72*points,-4.93*voltsdiv, self.freqStr)
        text(0.72*points,-4.4*voltsdiv, self.periodStr)
        
        show()

    def plot(self):
        # plain ole plot
        points=self.points
        trace=self.trace
        plot(trace)
        miny=trace.min()
        maxy=trace.max()
        vrange=maxy-miny
        miny=miny-0.1*vrange
        maxy=maxy+0.1*vrange
        vrange=maxy-miny
        axis([0,points,miny, maxy])
        xlabel(self.sweepStr)
        ylabel(self.voltStr)
        theaxes = gca()
        theaxes.set_xticklabels([])
        if not theaxes.is_first_col():
            theaxes.set_yticklabels([])
        if not theaxes.is_last_row():
            theaxes.set_xticklabels([])
        grid(1)

        low=0.02
        high=0.07
        text(0.03*points,miny+low*vrange, self.peakStr)
        text(0.03*points,miny+high*vrange, self.meanStr)
        text(0.72*points,miny+low*vrange, self.freqStr)
        text(0.72*points,miny+high*vrange, self.periodStr)
        
        show()
        
        
if __name__ == '__main__':
    tds2024 = TDS2024()
    tds2024.getSweepSetting()
    tds2024.prepare()
    tds2024.setChannel('CH3')
    tds2024.getVerticalSetting()
    tds2024.getMeasurements()
    tds2024.curve()
    tds2024.plot()
