"""Memory management: page replacement (FIFO, LRU, Optimal) and contiguous allocation
(first fit, best fit, worst fit)."""

from dataclasses import dataclass, field

from .logger import get_logger
from .validation import ValidationError, require_int, require_list

log = get_logger("memory")

PAGE_ALGORITHMS = ("FIFO", "LRU", "OPTIMAL")
FIT_STRATEGIES = ("FIRST", "BEST", "WORST")


# ---------------------------------------------------------------- page replacement
@dataclass
class PagingResult:
    algorithm: str
    frames: int
    references: list
    faults: int = 0
    hits: int = 0
    trace: list = field(default_factory=list)   # one dict per reference

    @property
    def fault_rate(self):
        return round(100 * self.faults / len(self.references), 2)

    @property
    def hit_ratio(self):
        return round(100 * self.hits / len(self.references), 2)


def _validate_paging(references, frames):
    references = require_list(references, "Reference string", 1)
    references = [require_int(r, "Page number", minimum=0) for r in references]
    frames = require_int(frames, "Number of frames", minimum=1, maximum=100)
    return references, frames


def page_replacement(references, frames, algorithm):
    """Simulate one page-replacement algorithm and keep a step-by-step trace."""
    algorithm = str(algorithm).upper()
    if algorithm not in PAGE_ALGORITHMS:
        raise ValidationError(f"Unknown page-replacement algorithm {algorithm!r}. Choose from {', '.join(PAGE_ALGORITHMS)}")
    references, frames = _validate_paging(references, frames)
    result = PagingResult(algorithm, frames, references)

    memory = []          # pages currently in frames, in frame order
    loaded_at = {}       # page -> time it was loaded (FIFO order)
    last_used = {}       # page -> time it was last referenced (LRU)
    for t, page in enumerate(references):
        evicted = None
        if page in memory:
            result.hits += 1
            status = "HIT"
        else:
            result.faults += 1
            status = "FAULT"
            if len(memory) < frames:
                memory.append(page)
            else:
                if algorithm == "FIFO":
                    victim = min(memory, key=lambda p: loaded_at[p])
                elif algorithm == "LRU":
                    victim = min(memory, key=lambda p: last_used[p])
                else:  # OPTIMAL: page used farthest in the future; never-used pages first
                    future = references[t + 1:]
                    victim = max(memory, key=lambda p: (future.index(p) if p in future else len(future) + 1,
                                                        -loaded_at[p]))
                memory[memory.index(victim)] = page
                evicted = victim
            loaded_at[page] = t
        last_used[page] = t
        result.trace.append({"step": t + 1, "page": page, "frames": list(memory),
                             "status": status, "evicted": evicted})
    log.info("%s with %d frames on %d references: %d faults", algorithm, frames,
             len(references), result.faults)
    return result


def compare_paging(references, frames):
    return [page_replacement(references, frames, a) for a in PAGE_ALGORITHMS]


def frames_sweep(references, frame_counts):
    """Faults for every algorithm at each frame count: {algorithm: [faults...]}"""
    return {a: [page_replacement(references, f, a).faults for f in frame_counts] for a in PAGE_ALGORITHMS}


def belady_check(references, frame_counts):
    """Return the frame counts where FIFO gets MORE faults with MORE frames (Belady's anomaly)."""
    faults = [page_replacement(references, f, "FIFO").faults for f in frame_counts]
    return [(frame_counts[i], faults[i], frame_counts[i + 1], faults[i + 1])
            for i in range(len(frame_counts) - 1) if faults[i + 1] > faults[i]]


# ---------------------------------------------------------------- contiguous allocation
@dataclass
class AllocationResult:
    strategy: str
    blocks: list                     # original block sizes
    remaining: list = field(default_factory=list)
    allocations: list = field(default_factory=list)   # dicts: pid, size, block, left
    waiting: list = field(default_factory=list)       # dicts: pid, size

    @property
    def total_memory(self):
        return sum(self.blocks)

    @property
    def allocated(self):
        return sum(a["size"] for a in self.allocations)

    @property
    def utilization(self):
        return round(100 * self.allocated / self.total_memory, 2)

    @property
    def free_left(self):
        return sum(self.remaining)

    @property
    def largest_free(self):
        return max(self.remaining) if self.remaining else 0


def contiguous_allocation(blocks, requests, strategy):
    """Place each request in a free block using first, best or worst fit.

    blocks:   list of free block sizes (KB)
    requests: list of {"pid": "P1", "size": 212} (or (pid, size) pairs)
    A block that is partly used keeps its leftover space for later requests.
    """
    strategy = str(strategy).upper()
    if strategy not in FIT_STRATEGIES:
        raise ValidationError(f"Unknown fit strategy {strategy!r}. Choose from {', '.join(FIT_STRATEGIES)}")
    blocks = [require_int(b, "Block size", minimum=1) for b in require_list(blocks, "Memory blocks", 1)]
    clean = []
    for i, r in enumerate(require_list(requests, "Process requests", 1)):
        if isinstance(r, (list, tuple)):
            r = {"pid": r[0], "size": r[1]}
        pid = str(r.get("pid") or f"P{i + 1}")
        clean.append({"pid": pid, "size": require_int(r.get("size"), f"{pid} size", minimum=1)})

    result = AllocationResult(strategy, blocks, remaining=list(blocks))
    for req in clean:
        fits = [i for i, free in enumerate(result.remaining) if free >= req["size"]]
        if not fits:
            result.waiting.append(req)
            continue
        if strategy == "FIRST":
            chosen = fits[0]
        elif strategy == "BEST":
            chosen = min(fits, key=lambda i: (result.remaining[i], i))
        else:
            chosen = max(fits, key=lambda i: (result.remaining[i], -i))
        result.remaining[chosen] -= req["size"]
        result.allocations.append({"pid": req["pid"], "size": req["size"],
                                   "block": chosen + 1, "left": result.remaining[chosen]})
    log.info("%s fit: %d/%d requests allocated, %d KB free left", strategy,
             len(result.allocations), len(clean), result.free_left)
    return result


def compare_fits(blocks, requests):
    return [contiguous_allocation(blocks, requests, s) for s in FIT_STRATEGIES]
