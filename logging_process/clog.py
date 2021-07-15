import io
import os
import sys
import time

from portalocker import LOCK_EX, lock, unlock
from contextlib import contextmanager
from secrets import randbits

from logging.handlers import BaseRotatingHandler, TimedRotatingFileHandler
from logging import FileHandler


_MIDNIGHT = 24 * 60 * 60  # number of seconds in a day

PY2 = False
if sys.version_info[0] == 2:
    PY2 = True


# 根据开源包 ConcurrentRotatingFileHandler 抽象出的文件锁类
class ConcurrentLock(FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=False, umask=None):
        """
        Use the specified filename for streamed logging
        """
        self.mode = mode
        self.encoding = encoding
        FileHandler.__init__(self, filename, mode, encoding, delay)

        self.terminator = "\n"
        self.lockFilename = self.getLockFilename()
        self.is_locked = False
        self.stream_lock = None
        self.umask = umask
        self.unicode_error_policy = 'ignore'

    def getLockFilename(self):
        """
        Decide the lock filename. If the logfile is file.log, then we use `.__file.lock` and
        not `file.log.lock`. This only removes the extension if it's `*.log`.
        :return: the path to the lock file.
        """
        if self.baseFilename.endswith(".log"):
            lock_file = self.baseFilename[:-4]
        else:
            lock_file = self.baseFilename
        lock_file += ".lock"
        lock_path, lock_name = os.path.split(lock_file)
        # hide the file on Unix and generally from file completion
        lock_name = ".__" + lock_name
        return os.path.join(lock_path, lock_name)

    def _open_lockfile(self):
        if self.stream_lock and not self.stream_lock.closed:
            return
        lock_file = self.lockFilename

        with self._alter_umask():
            self.stream_lock = open(lock_file, "wb", buffering=0)

    def _open(self, mode=None):
        # Normally we don't hold the stream open. Only do_open does that
        # which is called from do_write().
        return None

    def do_open(self, mode=None):
        """
        Open the current base file with the (original) mode and encoding.
        Return the resulting stream.
        Note:  Copied from stdlib.  Added option to override 'mode'
        使用（原始）模式和编码打开当前基本文件。
        返回结果流。
        注：从stdlib复制。添加了覆盖“模式”的选项
        """
        if mode is None:
            mode = self.mode
        with self._alter_umask():
            stream = io.open(self.baseFilename, mode=mode)
        return stream

    @contextmanager
    def _alter_umask(self):
        """Temporarily alter umask to custom setting, if applicable 临时将umask更改为自定义设置（如果适用）"""
        if self.umask is None:
            yield  # nothing to do
        else:
            prev_umask = os.umask(self.umask)
            try:
                yield
            finally:
                os.umask(prev_umask)

    def _close(self):
        """ Close file stream.  Unlike close(), we don't tear anything down, we
        expect the log to be re-opened after rotation."""

        if self.stream:
            try:
                if not self.stream.closed:
                    # Flushing probably isn't technically necessary, but it feels right
                    self.stream.flush()
                    self.stream.close()
            finally:
                self.stream = None

    def flush(self):
        """Does nothing; stream is flushed on each write."""
        return

    def do_write(self, msg):
        """Handling writing an individual record; we do a fresh open every time.
        This assumes emit() has already locked the file."""
        self.stream = self.do_open()
        stream = self.stream
        if PY2:
            self.do_write_py2(msg)
        else:
            msg = msg + self.terminator
            try:
                stream.write(msg)
            except UnicodeError:
                # Try to emit in a form acceptable to the output encoding
                # The unicode_error_policy determines whether this is lossy.
                try:
                    encoding = getattr(stream, 'encoding', self.encoding or 'us-ascii')
                    msg_bin = msg.encode(encoding, self.unicode_error_policy)
                    msg = msg_bin.decode(encoding, self.unicode_error_policy)
                    stream.write(msg)
                except UnicodeError:
                    raise

        stream.flush()
        self._close()
        return

    # noinspection PyCompatibility,PyUnresolvedReferences
    def do_write_py2(self, msg):
        stream = self.stream
        term = self.terminator
        policy = self.unicode_error_policy
        encoding = getattr(stream, 'encoding', None)

        # as far as I can tell, this should always be set from io.open, but just in case...
        if not encoding:
            encoding = self.encoding or 'utf-8'

        if not isinstance(msg, unicode):
            msg = unicode(msg, encoding, policy)

        # Add in the terminator.
        if not isinstance(term, unicode):
            term = unicode(term, encoding, policy)
        msg = msg + term
        stream.write(msg)

    def _do_lock(self):
        if self.is_locked:
            raise   # already locked... recursive?
        self._open_lockfile()
        if self.stream_lock:
            for i in range(10):
                # noinspection PyBroadException
                try:
                    lock(self.stream_lock, LOCK_EX)
                    self.is_locked = True
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError("Cannot acquire lock after 10 attempts")

    def _do_unlock(self):
        if self.stream_lock:
            if self.is_locked:
                unlock(self.stream_lock)
                self.is_locked = False
            self.stream_lock.close()
            self.stream_lock = None


# 继承TimedRotatingFileHandler类，然后修改了doRollover方法，和emit方法
class MyTimedRotatingFileHandler(TimedRotatingFileHandler, ConcurrentLock):
    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False, atTime=None):
        TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, encoding, delay, utc, atTime)
        ConcurrentLock.__init__(self, filename, 'a', encoding, delay)
        self.nameFormat = "{basePath}/{filename}.{suffix}"

    def shouldRollover(self, record):
        del record
        return self._shouldRollover()

    def _shouldRollover(self):
        self.stream = self.do_open()
        t = int(time.time())
        if t >= self.rolloverAt:
            return 1
        self._close()
        return 0

    def doRollover(self):
        self._close()
        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)

        # dfn = "%s.%s" % (self.baseFilename, time.strftime(self.suffix, timeTuple))
        basePath = os.path.dirname(self.baseFilename)
        filename = os.path.basename(self.baseFilename)
        dfn = self.nameFormat.format(basePath=basePath, filename=filename, suffix=time.strftime(self.suffix, timeTuple))
        # if os.path.exists(dfn):
        #     os.remove(dfn)
        if not os.path.exists(dfn) and os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, dfn)

        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        if not self.delay:
            self.stream = self.do_open()
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:
                    addend = -3600
                else:
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt

    def emit(self, record):
        """
            发出一个记录。从父类重写以在滚动和写入期间处理文件锁定。这也会在获取*锁之前格式化*以防格式本身记录内部的调用。锁定时也会发生翻转。
        """
        # noinspection PyBroadException
        try:
            msg = self.format(record)
            try:
                self._do_lock()
                try:
                    if self.shouldRollover(record):
                        self.doRollover()
                except Exception as e:
                    pass
                self.do_write(msg)
            finally:
                self._do_unlock()

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


# 重写了RotatingFileHandler方法
class MyRotatingFileHandler(BaseRotatingHandler, ConcurrentLock):
    """
    Handler for logging to a set of files, which switches from one file to the
    next when the current file reaches a certain size. Multiple processes can
    write to the log file concurrently, but this may mean that the file will
    exceed the given size.
    """
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=None):

        self.maxBytes = maxBytes
        self.backupCount = backupCount

        # Construct the handler with the given arguments in "delayed" mode
        # because we will handle opening the file as needed. File name
        # handling is done by FileHandler since Python 2.5.
        BaseRotatingHandler.__init__(self, filename, mode, encoding=encoding, delay=True)
        ConcurrentLock.__init__(self, filename, mode, encoding=encoding, delay=True)

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        self._close()
        if self.backupCount <= 0:
            self.stream = self.do_open("w")
            self._close()
            return

        tmpname = None
        while not tmpname or os.path.exists(tmpname):
            tmpname = "%s.rotate.%08d" % (self.baseFilename, randbits(64))
        try:
            # Do a rename test to determine if we can successfully rename the log file #执行重命名测试以确定是否可以成功重命名日志文件
            os.rename(self.baseFilename, tmpname)
        except (IOError, OSError):
            return

        def do_rename(source_fn, dest_fn):
            if os.path.exists(dest_fn):
                os.remove(dest_fn)
            if os.path.exists(source_fn):
                os.rename(source_fn, dest_fn)
        for i in range(self.backupCount - 1, 0, -1):
            sfn = "%s.%d" % (self.baseFilename, i)
            dfn = "%s.%d" % (self.baseFilename, i + 1)
            if os.path.exists(sfn):
                do_rename(sfn, dfn)
        dfn = self.baseFilename + ".1"
        do_rename(tmpname, dfn)

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.
        For those that are keeping track. This differs from the standard
        library's RotatingLogHandler class. Because there is no promise to keep
        the file size under maxBytes we ignore the length of the current record.
        确定是否应发生翻车。为了那些跟踪的人。这与标准库的RotatingLogHandler类不同。
        因为没有保证将文件大小保持在maxBytes以下，所以我们忽略了当前记录的长度。
        """
        del record  # avoid pychecker warnings
        return self._shouldRollover()

    def _shouldRollover(self):
        if self.maxBytes > 0:  # are we rolling over?
            self.stream = self.do_open()
            try:
                self.stream.seek(0, 2)  # due to non-posix-compliant Windows feature
                if self.stream.tell() >= self.maxBytes:
                    return True
            finally:
                self._close()
        return False

    def emit(self, record):
        """
            发出一个记录。从父类重写以在滚动和写入期间处理文件锁定。这也会在获取*锁之前格式化*以防格式本身记录内部的调用。锁定时也会发生翻转。
        """
        # noinspection PyBroadException
        try:
            msg = self.format(record)
            try:
                self._do_lock()
                try:
                    if self.shouldRollover(record):
                        self.doRollover()
                except Exception as e:
                    pass
                self.do_write(msg)
            finally:
                self._do_unlock()

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)