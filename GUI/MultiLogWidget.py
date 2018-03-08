#!/usr/bin/python
# -*- coding: utf-8 -*-

from random import randint
from PyQt4.QtCore import QPoint,QString,QSize, pyqtSignal
from PyQt4.QtGui import QMdiArea,QMdiSubWindow,QPlainTextEdit,QVBoxLayout,QPushButton,QApplication,QWidget,\
    QTextBrowser
from Common.Log import LOG_LEVEL_INFO, LogLevelNames
import os
import time
from threading import Lock
import threading

###############################################################################

LogColorsForLevel = ["purple", "red", "orange", "green", None, None, None]
        
###############################################################################

class LogWindow(QMdiSubWindow):

    flush_signal = pyqtSignal(str)

    #--------------------------------------------------------------------#
    
    def __init__(self, title):
        super(LogWindow, self).__init__()
        self.flush_signal.connect(self.flush)
        self._widget = QMdiSubWindow()
        self._widget.setWindowTitle(title)
        self._te_log = QTextBrowser()
        self._te_log.setLineWrapMode(QTextBrowser.NoWrap)
        #self._te_log.setMaximumBlockCount(100) 
        #self._te_log.anchorClicked.connect(self._onAnchorClicked)
        #self._te_log.setOpenLinks(False)
        self._te_log.setStyleSheet("""
            font-family: monospace;
            white-space: pre;            
        """)
        self.layout().addWidget(self._te_log)
        
    #--------------------------------------------------------------------#
    
    def flush(self, html):
        scrollbar = self._te_log.verticalScrollBar()
        follow = scrollbar.value() == scrollbar.maximum()
        self._te_log.append(html)
        if follow:
            scrollbar.setValue(scrollbar.maximum())        
        
    
###############################################################################

class LogItem(object):
    
    def __init__(self, owner, log_id, source = None):
        super(LogItem, self).__init__()
        self._id = log_id
        self._owner = owner
        self._buffer = ""
        self._buffer_lock = Lock()
        self._last_flush_time = 0
        self._flush_rate = 0.1
        self._widget = None

    #--------------------------------------------------------------------#
    
    def _onAnchorClicked(self, url):
        path = url.toString()
        if url.isLocalFile() or os.path.isfile(path):
            path = os.path.abspath(str(path))
            log = self._owner.open(path, source_path=path)
            log.setFocus()
        else:
            print "External link: %s" % path
        
    #--------------------------------------------------------------------#
    
    def open(self, title):
        title = "<Empty>" if title is None else str(title)        
        if self._widget is None:
            self._widget = LogWindow(title)
        return self._widget

    #--------------------------------------------------------------------#
    
    def window(self):
        return self._widget
    
    #--------------------------------------------------------------------#
    
#     def _highlightLinks(self, line):
#         words = line.split()
#         for word in words:
#             is_file = os.path.isfile(word)
#             is_log_file = is_file and (word.endswith(".log") or word.endswith(".txt") or word.endswith(".html"))
#             is_csv_file = is_file and (word.endswith(".csv"))
#             is_url = validators.url(word)
#             if is_log_file or is_url:
#                 line = line.replace(word, "<a href='%s'>%s</a>" % (word, word))
        
    #--------------------------------------------------------------------#
    
    def flush(self):
        bps = len(self._buffer) / self._flush_rate
        now = time.time()
        if now - self._last_flush_time < self._flush_rate:
            return
         
        self._last_flush_time = now
        if len(self._buffer) == 0:
            return

        if self._widget is not None:
            with self._buffer_lock:
                self._widget.flush_signal.emit(self._buffer)
            self._buffer = ""
                
    #--------------------------------------------------------------------#
    
    def append(self, line, log_level = LOG_LEVEL_INFO):
        line = QString.fromUtf8(line)
        line = unicode(line)
                 
        line = line.replace("  ", " &nbsp;")
            
        color = LogColorsForLevel[log_level]
        if color is None:
            line = "<font>%s</font>" % (line)
        else:
            line = "<font family='monospace' color='%s'>%s</font>" % (color, line)

        with self._buffer_lock:
            if len(self._buffer) > 0:
                self._buffer += "<br>" 
            self._buffer += line

    #--------------------------------------------------------------------#
    
    def close(self):
        pass
        
###############################################################################

class MultiLogWidget(QMdiArea):
    
    class GlobalLog(object):
        def __repr__(self):
            return "main"
        
    GLOBAL_LOG = GlobalLog()
    SUB_WINDOW_DEFAULT_RATIO_X = 0.7
    SUB_WINDOW_DEFAULT_RATIO_Y = 0.7
    CASCADE_SKIP_PIXELS_X = 22
    CASCADE_SKIP_PIXELS_Y = 22
    
    #--------------------------------------------------------------------#
    
    def __init__(self, logs_folder = None, parent = None):
        super(MultiLogWidget, self).__init__(parent)
        self._logs = {}
        self._logs_folder = logs_folder 
        self._logs_lock = Lock()
        self.cascade_x_id = 0
        self.cascade_y_id = 0

        self._flush_rate = 0.5
        threading.Timer(self._flush_rate, self._flushAll).start()
        
        self._initGui()
        
    #--------------------------------------------------------------------#
    
    def _initGui(self):
        pass

    #--------------------------------------------------------------------#

    def _flushAll(self):
        # print "Flusing at %s" % str(time.time())
        for log in self._logs.values():
            log.flush()
        if self.isVisible():            
            threading.Timer(self._flush_rate, self._flushAll).start()
            
    #--------------------------------------------------------------------#
    
    def _getNextWindowPosition(self):
        x = self.cascade_x_id * MultiLogWidget.CASCADE_SKIP_PIXELS_X
        y = self.cascade_y_id * MultiLogWidget.CASCADE_SKIP_PIXELS_Y
        if y > (1 - MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_X) * self.height():
            y = 0
            self.cascade_y_id = 0
        if x > (1 - MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_Y) * self.width():
            x = 0
            self.cascade_x_id = 0
        self.cascade_x_id += 1
        self.cascade_y_id += 1
        return QPoint(x,y)
        
    #--------------------------------------------------------------------#
    
    def _getOrCreateLog(self, log_id):
        with self._logs_lock:
            if log_id in self._logs:
                return self._logs[log_id]
            log = LogItem(self, log_id)
            self._logs[log_id] = log
            return log
    
    #--------------------------------------------------------------------#
    
    def _removeLog(self, log_id):
        if log_id in self._logs:
            return self._logs.pop(log_id)
        return None
        
    #--------------------------------------------------------------------#
    
    def setLogsFolder(self, logs_folder):
        self._logs_folder = logs_folder
        
    #--------------------------------------------------------------------#
    
    def open(self, log_id = GLOBAL_LOG, title = None, source_path = None):
        log = self._getOrCreateLog(log_id)
        if source_path is not None:
            with open(source_path, "r") as source:
                for line in source:
                    log.append(line)
        
        
        window = log.window()
        if window is None:
            pos = self._getNextWindowPosition()
            size = QSize(self.width() * MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_X, 
                         self.height() * MultiLogWidget.SUB_WINDOW_DEFAULT_RATIO_Y)
            window = log.open(title)
            self.addSubWindow(window)
            window.resize(size)
            window.move(pos)
        
        if not window.isVisible():
            window.show()
        return log 

    #--------------------------------------------------------------------#
    
    def close(self, log_id = GLOBAL_LOG):
        log = self._removeLog(log_id)
        if (log is not None) and log.window():
            log.close()
            self.removeSubWindow(log.window())
        if self.cascade_x_id > 0:
            self.cascade_x_id -= 1
        if self.cascade_y_id > 0:
            self.cascade_y_id -= 1            
    
    #--------------------------------------------------------------------#
    
    def isOpen(self, log_id):
        return (log_id in self._logs) and (self._logs[log_id].window())
        
    #--------------------------------------------------------------------#
    
    def log(self, line, log_id = GLOBAL_LOG, log_level = LOG_LEVEL_INFO):
        log = self._getOrCreateLog(log_id)
        log.append(line, log_level)
        
###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

x = 0
log_id = 0

#--------------------------------------------------------------------#

def test(): 
    global x
    global log_id
    
    log_level = randint(0, 5)
    if not mlog.isOpen(log_id):
        mlog.open(log_id, "Title for log #%u" % log_id)
    mlog.log("☀ %s Line #%u ☀ SPACES: #      # http://www.kikar.co.il" % (LogLevelNames[log_level], x), log_id, log_level)
    mlog.log("More: test.log", log_id)
    x += 1
    log_id = (log_id + 1) % 8

#--------------------------------------------------------------------#
       
if __name__ == '__main__':
    app = QApplication([])
    prompt = QWidget()
    prompt.setLayout(QVBoxLayout())
    mlog = MultiLogWidget(".")
    
    button = QPushButton("Push me")
    button.clicked.connect(test)

    prompt.layout().addWidget(mlog)
    prompt.layout().addWidget(button)

    prompt.resize(QSize(800, 600))
    prompt.show()
    #prompt.setData([[7,0,1,2],[8,3,4,5]], ["R","F","G","H"], ["S","T"])
    app.exec_()
