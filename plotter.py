from matplotlib import rc, use
rc('text', usetex=False)
rc('font', family='monospace')  # LOOKs like a scope  ;-)
# WXAgg: problems with draw below() .... use ginput() ???
# GtkAgg: /usr/lib/python2.7/dist-packages/matplotlib/backends/backend_gtk.py:253:
#         Warning: Source ID 5 was not found when attempting to remove it
#  gobject.source_remove(self._idle_event_id)
use("TkAgg")

from matplotlib.pyplot import plot, axis, xlabel, ylabel, gca, grid, text, show, figure, xticks, title, rcParams, savefig
try:
    rcParams['savefig.directory'] = None  # use default
except KeyError:
    pass

from numpy import arange

class ScopeDisplay(object):
    colorD = {1:'yellow', 2: 'aqua', 3: 'purple', 4: 'darkgreen'} # approx channel colors

    def __init__(self, instr, idStr, disp=False, save=True):
        self.instr=instr
        self.idStr=idStr
        self.figL=[]
        self.tag=None
        self.cidD={}
        self.save=save  # should come up with some graphical way to ask for annotate/save
        if disp: self.display()

    def display(self):
        chNL = [ ch for ch in range(1,5)  if self.instr.channelWasAcq(ch) ]
        for ch in chNL:
            self.plotChannel(ch, scopeView=False)
        self.plotAll(chNL)
        if self.save: self.annotate_plots()
        self.show()

    def plotAll(self, chNL):
        f=figure('CHALL')
        self.figL.append(f)
        measD={}
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
                # use fixed width font???
                text( x, y, m , color=self.colorD[chN], backgroundcolor='silver', size=6, family= 'monospace')  
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
            #ylabel(chan.voltStr, size=labelSz)
            text(-.75, 3-chN, chan.voltStr, color=self.colorD[chN], backgroundcolor='silver', size=8, family= 'monospace' )
            theaxes.set_yticklabels([])
            # place trigger location, channel color, and zero baseline per channel, color
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
            savefig('Traces/'+fig.get_label()+'-'+self.idStr+'.png')

    def annotate_plots(self):
        # add an annotation to zero or more of the plots for the current data acquisition

        for fig in self.figL:
            cid = fig.canvas.mpl_connect('button_press_event', self.onclick)
            self.cidD[fig]=cid
            fig.show()
            
        if not self.tag:
            self.tag = raw_input("Enter a tag description: ")

    def show(self):
        show()

if __name__ == '__main__':
    tag = raw_input('Enter: ')
    print tag
