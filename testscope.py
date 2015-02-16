from tekscope import TektronixScope
from plotter import ScopeDisplay


_dicts = """
{'COUP': 'DC', 'LEVEL': 4.56, 'STATE': 'SAVE', 'SLO': 'FALL', 'SOU': 'CH3', 'MODE': 'NORMAL', 'HOLDO': 5e-07, 'TYPE': 'EDGE'}

{'WFID': 'Ch1, DC coupling, 5.0E-1 V/div, 5.0E-2 s/div, 2500 points,
Sample mode', 'BIT_NR': 8, 'YUNIT': 'Volts', 'XZERO': -0.15,
'PT_OFF': 0, 'PT_FMT': 'Y', 'BN_FMT': 'RI', 'BYT_NR': 1, 'ENCDG':
'BIN', 'NR_PT': 2500, 'XUNIT': 's', 'YMULT': 0.02, 'XINCR': 0.0002,
'YOFF': -166.0, 'BYT_OR': 'LSB', 'YZERO': 0.0}
"""
_cmdStr = """    
TRIGGER:MAIN:LEVEL 4.56
TRIGGER:MAIN:MODE NORMAL
TRIGGER:MAIN:EDGE:SOU CH3
TRIGGER:MAIN:TYPE EDGE
acquire:state on
DATA:SOURCE CH1
measu:imm:typ FALL;:measu:imm:sou CH1
measu:imm:typ FALL;:measu:imm:sou CH2
measu:imm:typ RISE;:measu:imm:sou CH1
measu:imm:typ RISE;:measu:imm:sou CH2
measu:imm:typ PK2P;:measu:imm:sou CH1
measu:imm:typ PK2P;:measu:imm:sou CH2
measu:imm:typ CRMS;:measu:imm:sou CH1
measu:imm:typ CRMS;:measu:imm:sou CH2
DATA:SOURCE CH2
measu:imm:typ FALL;:measu:imm:sou CH3
measu:imm:typ RISE;:measu:imm:sou CH3
measu:imm:typ PK2P;:measu:imm:sou CH3
measu:imm:typ CRMS;:measu:imm:sou CH3
DATA:SOURCE CH3
acquire:state off
"""
_reqStr = """
TRIG:STATE?
:TRIGGER:STATE SAVE
TRIGGER:MAIN:HOLDO?
:TRIGGER:MAIN:HOLDOFF:VALUE 5.0E-7
TRIGGER:MAIN:TYPE?
:TRIGGER:MAIN:TYPE EDGE
TRIGGER:MAIN:MODE?
:TRIGGER:MAIN:MODE NORMAL
TRIGGER:MAIN:LEVEL?
:TRIGGER:MAIN:LEVEL 4.56E0
TRIGGER:MAIN:EDGE:COUP?
:TRIGGER:MAIN:EDGE:COUPLING DC
TRIGGER:MAIN:EDGE:SLO?
:TRIGGER:MAIN:EDGE:SLOPE FALL
TRIGGER:MAIN:EDGE:SOU?
:TRIGGER:MAIN:EDGE:SOURCE CH3
hor:mai:sca?
:HORIZONTAL:MAIN:SCALE 5.0E-2
CH1:scale?
:CH1:SCALE 5.0E-1
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 0.0E0
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 0.0E0
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 1.400003433E-1
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 4.8800115585E0
wfmpre?
:WFMPRE:BYT_NR 1;BIT_NR 8;ENCDG BIN;BN_FMT RI;BYT_OR LSB;NR_PT 2500;WFID "Ch1, DC coupling, 5.0E-1 V/div, 5.0E-2 s/div, 2500 points, Sample mode";PT_FMT Y;XINCR 2.0E-4;PT_OFF 0;XZERO -1.5E-1;XUNIT "s";YMULT 2.0E-2;YZERO 0.0E0;YOFF -1.66E2;YUNIT "Volts"
curv?
[ 4.88  4.88  4.86 ...,  4.88  4.88  4.9 ]
CH2:scale?
:CH2:SCALE 5.0E-1
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 0.0E0
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 0.0E0
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 1.400003433E-1
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 4.8634057045E0
wfmpre?
:WFMPRE:BYT_NR 1;BIT_NR 8;ENCDG BIN;BN_FMT RI;BYT_OR LSB;NR_PT 2500;WFID "Ch2, DC coupling, 5.0E-1 V/div, 5.0E-2 s/div, 2500 points, Sample mode";PT_FMT Y;XINCR 2.0E-4;PT_OFF 0;XZERO -1.5E-1;XUNIT "s";YMULT 2.0E-2;YZERO 0.0E0;YOFF -1.91E2;YUNIT "Volts"
curv?
[ 4.86  4.86  4.82 ...,  4.84  4.88  4.88]
CH3:scale?
:CH3:SCALE 5.0E-1
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 4.0E-4
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 1.4E-3
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 9.99999046E-2
measu:imm:val?
:MEASUREMENT:IMMED:VALUE 4.9288582802E0
wfmpre?
:WFMPRE:BYT_NR 1;BIT_NR 8;ENCDG BIN;BN_FMT RI;BYT_OR LSB;NR_PT 2500;WFID "Ch3, DC coupling, 5.0E-1 V/div, 5.0E-2 s/div, 2500 points, Sample mode";PT_FMT Y;XINCR 2.0E-4;PT_OFF 0;XZERO -1.5E-1;XUNIT "s";YMULT 2.0E-2;YZERO 0.0E0;YOFF -2.21E2;YUNIT "Volts"
curv?
got from Serial: [ 4.9   4.94  4.92 ...,  4.94  4.92  4.94]

"""
_reqL = iter( _reqStr[1:-1].split('\n'))

class DummyScope(TektronixScope):
    _idStr = 'Dummy'
    _rbuf = None
    _vars = {}
    while 1:
        kreq = _reqL.next()
        print req, 
        resp = _reqL.next()
        print resp
    
    def connect(self):
        pass
    def clear(self):
        self._haveCmd = 0
    def identify(self):
        pass
    
    def read(self):
        # feed back byte of response
        byt = self._rbuf[0]
        if byt!='\n':
            self._rbuf = self._rbuf[1:]
        else:
            self._rbuf=None
        return byt
    
    def readline(self):
        # feedback all of response
        return self.rbuf
    
    def _req(self, buf):
        print 'req: ', buf
        self._rbuf=''
        
    def _cmd(self, key, val):
        print 'set %s = %s '%(key, val)
        self._vars[key]=val
        self._rbuf=None

    def write(self, buf):
        buf=buf.strip()
        if buf[-1]=='?':
            self._req(buf)
            return
        bufL = buf.split(' ')
        n = len(bufL)
        if n==2: # set
            self._cmd(bufL[0], bufL[1])
            return 
            
if __name__=='__main__':
    tds2024 = DummyScope()
    mT = ('FALL', 'RISE', 'PK2P', 'CRMS')
    tds2024.setTrigger(level=4.56, holdo=None, mode='NORMAL', typ='EDGE', trigD={'SOU':'CH3'})
    print tds2024.getTrigger(forceAcq=True)
    acqD =  {3:mT, 2: mT, 1: mT}
    tds2024.acquire(acqD )
    pl=ScopeDisplay(tds2024)
    pl.plotChannel(3)
    pl.plotChannel(2, scopeView=False)
    pl.plotChannel(1, scopeView=False)    
    pl.plotAll()
    pl.annotate_plots( )
    pl.show()
    
