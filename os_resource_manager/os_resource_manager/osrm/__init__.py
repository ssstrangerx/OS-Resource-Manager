"""OS Resource Manager: a simulator for core operating-system resource-management functions.

Modules
-------
scheduling : CPU scheduling (FCFS, SJF, SRTF, Priority NP/P, Round Robin)
memory     : page replacement (FIFO, LRU, Optimal) and contiguous allocation (first/best/worst fit)
deadlock   : Banker's safety and request algorithms, deadlock detection and recovery
storage    : disk scheduling (FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK)
reporting  : tables, ASCII charts, CSV files, PNG charts and the analysis report
analysis   : runs every module on the shared datasets and compares the algorithms
"""

__version__ = "1.0.0"
