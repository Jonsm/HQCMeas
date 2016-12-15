# -*- coding: utf-8 -*-
# =============================================================================
# module : alazar935x.py
# author : Benjamin Huard & Nathanael Cottet & Sébastien Jezouin
# license : MIT license
# =============================================================================
"""

This module defines drivers for Alazar using DLL Library.

:Contains:
    Alazar987x

To read well the Dll of the Alazar9870, Visual C++ Studio is needed.

"""
import os
import time
import math
import numpy as np
import ctypes
from inspect import cleandoc

from pyclibrary import CLibrary

from ..dll_tools import DllInstrument

class DMABuffer:
    '''Buffer suitable for DMA transfers.

    AlazarTech digitizers use direct memory access (DMA) to transfer
    data from digitizers to the computer's main memory. This class
    abstracts a memory buffer on the host, and ensures that all the
    requirements for DMA transfers are met.

    DMABuffers export a 'buffer' member, which is a NumPy array view
    of the underlying memory buffer

    Args:

      bytes_per_sample (int): The number of bytes per samples of the
      data. This varies with digitizer models and configurations.

      size_bytes (int): The size of the buffer to allocate, in bytes.

    '''
    def __init__(self, bytes_per_sample, size_bytes):
        self.size_bytes = size_bytes
        ctypes.cSampleType = ctypes.c_uint8
        npSampleType = np.uint8
        if bytes_per_sample > 1:
            ctypes.cSampleType = ctypes.c_uint16
            npSampleType = np.uint16

        self.addr = None
        if os.name == 'nt':
            MEM_COMMIT = 0x1000
            PAGE_READWRITE = 0x4
            ctypes.windll.kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_long,
                                                     ctypes.c_long, ctypes.c_long]
            ctypes.windll.kernel32.VirtualAlloc.restype = ctypes.c_void_p
            self.addr = ctypes.windll.kernel32.VirtualAlloc(
                0, ctypes.c_long(size_bytes), MEM_COMMIT, PAGE_READWRITE)
        elif os.name == 'posix':
            ctypes.libc.valloc.argtypes = [ctypes.c_long]
            ctypes.libc.valloc.restype = ctypes.c_void_p
            self.addr = ctypes.libc.valloc(size_bytes)
        else:
            raise Exception("Unsupported OS")

        ctypes.ctypes_array = (ctypes.cSampleType *
                        (size_bytes // bytes_per_sample)
                        ).from_address(self.addr)
        self.buffer = np.frombuffer(ctypes.ctypes_array, dtype=npSampleType)
        pointer, read_only_flag = self.buffer.__array_interface__['data']

    def __exit__(self):
        if os.name == 'nt':
            MEM_RELEASE = 0x8000
            ctypes.windll.kernel32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_long]
            ctypes.windll.kernel32.VirtualFree.restype = ctypes.c_int
            ctypes.windll.kernel32.VirtualFree(ctypes.c_void_p(self.addr), 0, MEM_RELEASE)
        elif os.name == 'posix':
            ctypes.libc.free(self.addr)
        else:
            raise Exception("Unsupported OS")


class Alazar987x(DllInstrument):

    library = 'ATSApi.dll'

    def __init__(self, connection_info, caching_allowed=True,
                 caching_permissions={}, auto_open=True):

        super(Alazar987x, self).__init__(connection_info, caching_allowed,
                                         caching_permissions, auto_open)

        cache_path = unicode(os.path.join(os.path.dirname(__file__),
                                          'cache/Alazar.pycctypes.libc'))
        self._dll = CLibrary('ATSApi.dll',
                             ['AlazarError.h', 'AlazarCmd.h', 'AlazarApi.h'],
                             cache=cache_path, prefix=['Alazar'],
                             convention='windll')

    def open_connection(self):
        """Do not need to open a connection

        """
        pass

    def close_connection(self):
        """Do not need to close a connection

        """
        pass

    def configure_board(self):
        board = self._dll.GetBoardBySystemID(1,1)()
        # TODO: Select clock parameters as required to generate this
        # sample rate
        samplesPerSec = 1000000000.0
        self._dll.SetCaptureClock(board,
                                  self._dll.EXTERNAL_CLOCK_10MHz_REF,
                                  1000000000,
                                  self._dll.CLOCK_EDGE_RISING,
                                  1)
        # TODO: Select channel A input parameters as required.
        self._dll.InputControl(board,
                               self._dll.CHANNEL_A,
                               self._dll.DC_COUPLING,
                               self._dll.INPUT_RANGE_PM_400_MV,
                               self._dll.IMPEDANCE_50_OHM)

        # TODO: Select channel A bandwidth limit as required.
        self._dll.SetBWLimit(board, self._dll.CHANNEL_A, 0)


        # TODO: Select channel B input parameters as required.
        self._dll.InputControl(board, self._dll.CHANNEL_B,
                               self._dll.DC_COUPLING,
                               self._dll.INPUT_RANGE_PM_400_MV,
                               self._dll.IMPEDANCE_50_OHM)

        # TODO: Select channel B bandwidth limit as required.
        self._dll.SetBWLimit(board, self._dll.CHANNEL_B, 0)
        # TODO: Select trigger inputs and levels as required.
        self._dll.SetTriggerOperation(board, self._dll.TRIG_ENGINE_OP_J,
                                      self._dll.TRIG_ENGINE_J,
                                      self._dll.TRIG_EXTERNAL,
                                      self._dll.TRIGGER_SLOPE_POSITIVE,
                                      138,
                                      self._dll.TRIG_ENGINE_K,
                                      self._dll.TRIG_DISABLE,
                                      self._dll.TRIGGER_SLOPE_POSITIVE,
                                      128)

        # TODO: Select external trigger parameters as required.
        self._dll.SetExternalTrigger(board, self._dll.DC_COUPLING,
                                     self._dll.ETR_5V)

        # TODO: Set trigger delay as required.
        triggerDelay_sec = 0.
        triggerDelay_samples = int(triggerDelay_sec * samplesPerSec + 0.5)
        self._dll.SetTriggerDelay(board, triggerDelay_samples)

        # TODO: Set trigger timeout as required.
        #
        # NOTE: The board will wait for a for this amount of time for a
        # trigger event.  If a trigger event does not arrive, then the
        # board will automatically trigger. Set the trigger timeout value
        # to 0 to force the board to wait forever for a trigger event.
        #
        # IMPORTANT: The trigger timeout value should be set to zero after
        # appropriate trigger parameters have been determined, otherwise
        # the board may trigger if the timeout interval expires before a
        # hardware trigger event arrives.
        self._dll.SetTriggerTimeOut(board, 0)
        # Configure AUX I/O connector as required
        self._dll.ConfigureAuxIO(board, self._dll.AUX_OUT_TRIGGER,
                                 0)

    def get_demod(self, startaftertrig, duration, recordsPerCapture,
                  recordsPerBuffer, timestep, freq, average, NdemodA, NdemodB, NtraceA, NtraceB):

        board = self._dll.GetBoardBySystemID(1, 1)()

        # Number of samples per record: must be divisible by 32
        samplesPerSec = 1000000000.0
        samplesPerTrace = int(samplesPerSec * np.max(np.array(startaftertrig) + np.array(duration)))
        if samplesPerTrace % 32 == 0:
            samplesPerRecord = int(samplesPerTrace)
        else:
            samplesPerRecord = int((samplesPerTrace)/32 + 1)*32

        retCode = self._dll.GetChannelInfo(board)()
        bitsPerSample = self._dll.GetChannelInfo(board)[1]
        if retCode != self._dll.ApiSuccess:
            raise ValueError(cleandoc(self._dll.AlazarErrorToText(retCode)))

        # Compute the number of bytes per record and per buffer
        channel_number = 2 if ((NdemodA or NtraceA) and (NdemodB or NtraceB)) else 1  # Acquisition on A and B
        ret, (boardhandle, memorySize_samples,
              bitsPerSample) = self._dll.GetChannelInfo(board)
        bytesPerSample = (bitsPerSample + 7) // 8
        bytesPerRecord = bytesPerSample * samplesPerRecord
        bytesPerBuffer = int(bytesPerRecord * recordsPerBuffer*channel_number)

        # For converting data into volts
        channelRange = 0.4 # Volts
        bitsPerSample = 8
        code = (1 << (bitsPerSample - 1)) - 0.5

        bufferCount = int(round(recordsPerCapture / recordsPerBuffer))
        buffers = []
        for i in range(bufferCount):
            buffers.append(DMABuffer(bytesPerSample, bytesPerBuffer))

        # Set the record size
        self._dll.SetRecordSize(board, 0, samplesPerRecord)

        # Configure the number of records in the acquisition
#        acquisition_timeout_sec = 10
        self._dll.SetRecordCount(board, int(recordsPerCapture))

        # Calculate the number of buffers in the acquisition
        buffersPerAcquisition = round(recordsPerCapture / recordsPerBuffer)

        channelSelect = 1 if not (NdemodB or NtraceB) else (2 if not (NdemodA or NtraceA) else 3)
        self._dll.BeforeAsyncRead(board, channelSelect,  # Channels A & B
                                  0,
                                  samplesPerRecord,
                                  int(recordsPerBuffer),
                                  int(recordsPerCapture),
                                  self._dll.ADMA_EXTERNAL_STARTCAPTURE |
                                  self._dll.ADMA_NPT)()

        # Post DMA buffers to board. ATTENTION it is very important not to do "for buffer in buffers"
        for i in range(bufferCount):
            buffer = buffers[i]
            self._dll.PostAsyncBuffer(board, buffer.addr, buffer.size_bytes)

        start = time.clock()  # Keep track of when acquisition started
        self._dll.StartCapture(board)  # Start the acquisition

        # Preparation of the tables for the demodulation

        startSample = []
        samplesPerDemod = []
        samplesPerBlock = []
        NumberOfBlocks = []
        samplesMissing = []
        data = []
        dataExtended = []

        for i in range(NdemodA + NdemodB):
            startSample.append( int(samplesPerSec * startaftertrig[i]) )
            samplesPerDemod.append( int(samplesPerSec * duration[i]) )

            if timestep[i]:
                samplesPerBlock.append( samplesPerDemod[i] )
            else:
                # Check wheter it is possible to cut each record in blocks of size equal
                # to an integer number of periods
                periodsPerBlock = 1
                while (periodsPerBlock * samplesPerSec < freq[i] * samplesPerDemod[i]
                       and periodsPerBlock * samplesPerSec % freq[i]):
                    periodsPerBlock += 1
                samplesPerBlock.append( int(np.minimum(periodsPerBlock * samplesPerSec / freq[i],
                                                      samplesPerDemod[i])) )

            NumberOfBlocks.append( np.divide(samplesPerDemod[i], samplesPerBlock[i]) )
            samplesMissing.append( (-samplesPerDemod[i]) % samplesPerBlock[i] )
            # Makes the table that will contain the data
            data.append( np.empty((recordsPerCapture, samplesPerBlock[i])) )
            dataExtended.append( np.zeros((recordsPerBuffer, samplesPerDemod[i] + samplesMissing[i]),
                                          dtype='uint16') )

        for i in (np.arange(NtraceA + NtraceB) + NdemodA + NdemodB):
            startSample.append( int(samplesPerSec * startaftertrig[i]) )
            samplesPerDemod.append( int(samplesPerSec * duration[i]) )
            data.append( np.empty((recordsPerCapture, samplesPerDemod[i])) )

        start = time.clock()

        buffersCompleted = 0
        while buffersCompleted < buffersPerAcquisition:

            # Wait for the buffer at the head of the list of available
            # buffers to be filled by the board.
            buffer = buffers[buffersCompleted % len(buffers)]
            self._dll.WaitAsyncBufferComplete(board, buffer.addr, 10000)


            # Process data

            dataRaw = np.reshape(buffer.buffer, (recordsPerBuffer*channel_number, -1))

            for i in np.arange(NdemodA):
                dataExtended[i][:,:samplesPerDemod[i]] = dataRaw[:recordsPerBuffer,startSample[i]:startSample[i]+samplesPerDemod[i]]
                dataBlock = np.reshape(dataExtended[i],(recordsPerBuffer,-1,samplesPerBlock[i]))
                data[i][buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = np.sum(dataBlock, axis=1)

            for i in (np.arange(NdemodB) + NdemodA):
                dataExtended[i][:,:samplesPerDemod[i]] = dataRaw[(channel_number-1)*recordsPerBuffer:channel_number*recordsPerBuffer,startSample[i]:startSample[i]+samplesPerDemod[i]]
                dataBlock = np.reshape(dataExtended[i],(recordsPerBuffer,-1,samplesPerBlock[i]))
                data[i][buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = np.sum(dataBlock, axis=1)

            for i in (np.arange(NtraceA) + NdemodB + NdemodA):
                data[i][buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = dataRaw[:recordsPerBuffer,startSample[i]:startSample[i]+samplesPerDemod[i]]

            for i in (np.arange(NtraceB) + NtraceA + NdemodB + NdemodA):
                data[i][buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = dataRaw[(channel_number-1)*recordsPerBuffer:channel_number*recordsPerBuffer,startSample[i]:startSample[i]+samplesPerDemod[i]]

            buffersCompleted += 1

            self._dll.PostAsyncBuffer(board, buffer.addr, buffer.size_bytes)

        self._dll.AbortAsyncRead(board)

        for i in range(bufferCount):
            buffer = buffers[i]
            buffer.__exit__()

        print time.clock() - start
#        if time.clock() - start > acquisition_timeout_sec:
#            raise Exception("Error: Capture timeout. Verify trigger")
#            time.sleep(10e-3)

        # Normalize the np.sum and convert data into Volts
        for i in range(NdemodA + NdemodB):
            normalisation = 1 if samplesMissing[i] else 0
            data[i][:,:samplesPerBlock[i]-samplesMissing[i]] /= NumberOfBlocks[i] + normalisation
            data[i][:,samplesPerBlock[i]-samplesMissing[i]:] /= NumberOfBlocks[i]
            data[i] = (data[i] / code - 1) * channelRange
        for i in (np.arange(NtraceA + NtraceB) + NdemodA + NdemodB):
            data[i] = (data[i] / code - 1) * channelRange

        # calculate demodulation tables
        coses=[]
        sines=[]
        for i in range(NdemodA+NdemodB):
            dem = np.arange(samplesPerBlock[i])
            coses.append(np.cos(2. * math.pi * dem * freq[i] / samplesPerSec))
            sines.append(np.sin(2. * math.pi * dem * freq[i] / samplesPerSec))

        # prepare the structure of the answered array

        if (NdemodA or NdemodB):
            answerTypeDemod = []
            zerosDemodA = 1 + int(np.floor(np.log10(NdemodA))) if NdemodA else 0
            zerosDemodB = 1 + int(np.floor(np.log10(NdemodB))) if NdemodB else 0
            for i in range(NdemodA):
                answerTypeDemod += [('AI' + str(i).zfill(zerosDemodA), str(data[0].dtype)),
                                    ('AQ' + str(i).zfill(zerosDemodA), str(data[0].dtype))]
            for i in range(NdemodB):
                answerTypeDemod += [('BI' + str(i).zfill(zerosDemodB), str(data[0].dtype)),
                                    ('BQ' + str(i).zfill(zerosDemodB), str(data[0].dtype))]
            lengthDemod = [(samplesPerDemod[i]/int(samplesPerSec*timestep[i]) if timestep[i] else 1) for i in range(NdemodA+NdemodB)]
            biggerDemod = max(lengthDemod)
            print lengthDemod
        else:
            answerTypeDemod = 'f'
            biggerDemod = 0

        if (NtraceA or NtraceB):
            zerosTraceA = 1 + int(np.floor(np.log10(NtraceA))) if NtraceA else 0
            zerosTraceB = 1 + int(np.floor(np.log10(NtraceB))) if NtraceB else 0
            answerTypeTrace = ( [('A' + str(i).zfill(zerosTraceA), str(data[0].dtype)) for i in range(NtraceA)]
                              + [('B' + str(i).zfill(zerosTraceB), str(data[0].dtype)) for i in range(NtraceB)] )
            biggerTrace = np.max(samplesPerDemod[NdemodA+NdemodB:])
        else:
            answerTypeTrace = 'f'
            biggerTrace = 0

        if average:
            answerDemod = np.zeros(biggerDemod, dtype=answerTypeDemod)
            answerTrace = np.zeros(biggerTrace, dtype=answerTypeTrace)
        else:
            answerDemod = np.zeros((recordsPerCapture, biggerDemod), dtype=answerTypeDemod)
            answerTrace = np.zeros((recordsPerCapture, biggerTrace), dtype=answerTypeTrace)

        # Demodulate the data, average them if asked and return the result

        for i in np.arange(NdemodA+NdemodB):
            if i<NdemodA:
                Istring = 'AI' + str(i).zfill(zerosDemodA)
                Qstring = 'AQ' + str(i).zfill(zerosDemodA)
            else:
                Istring = 'BI' + str(i-NdemodA).zfill(zerosDemodB)
                Qstring = 'BQ' + str(i-NdemodA).zfill(zerosDemodB)
            angle = 2 * np.pi * freq[i] * startSample[i] / samplesPerSec
            if average:
                data[i] = np.mean(data[i], axis=0)
                ansI = 2 * np.mean((data[i]*coses[i]).reshape(lengthDemod[i], -1), axis=1)
                ansQ = 2 * np.mean((data[i]*sines[i]).reshape(lengthDemod[i], -1), axis=1)
                answerDemod[Istring][:lengthDemod[i]] = ansI * np.cos(angle) - ansQ * np.sin(angle)
                answerDemod[Qstring][:lengthDemod[i]] = ansI * np.sin(angle) + ansQ * np.cos(angle)
            else:
                ansI = 2 * np.mean((data[i]*coses[i]).reshape(recordsPerCapture, lengthDemod[i], -1), axis=2)
                ansQ = 2 * np.mean((data[i]*sines[i]).reshape(recordsPerCapture, lengthDemod[i], -1), axis=2)
                answerDemod[Istring][:,:lengthDemod[i]] = ansI * np.cos(angle) - ansQ * np.sin(angle)
                answerDemod[Qstring][:,:lengthDemod[i]] = ansI * np.sin(angle) + ansQ * np.cos(angle)

        for i in (np.arange(NtraceA+NtraceB) + NdemodB+NdemodA):
            if i<NdemodA+NdemodB+NtraceA:
                Tracestring = 'A' + str(i-NdemodA-NdemodB).zfill(zerosTraceA)
            else:
                Tracestring = 'B' + str(i-NdemodA-NdemodB-NtraceA).zfill(zerosTraceB)
            if average:
                answerTrace[Tracestring][:samplesPerDemod[i]] = np.mean(data[i], axis=0)
            else:
                answerTrace[Tracestring][:,:samplesPerDemod[i]] = data[i]

        return answerDemod, answerTrace

    def get_traces(self, timeaftertrig, recordsPerCapture,
                   recordsPerBuffer, average):

        board = self._dll.GetBoardBySystemID(1, 1)()

        # Number of samples per record: must be divisible by 32
        samplesPerSec = 1000000000.0
        samplesPerTrace = samplesPerSec*timeaftertrig
        if samplesPerTrace % 32 == 0:
            samplesPerRecord = int(samplesPerTrace)
        else:
            samplesPerRecord = int((samplesPerTrace)/32 + 1)*32

        retCode = self._dll.GetChannelInfo(board)()
        bitsPerSample = self._dll.GetChannelInfo(board)[1]
        if retCode != self._dll.ApiSuccess:
            raise ValueError(cleandoc(self._dll.AlazarErrorToText(retCode)))

        # Compute the number of bytes per record and per buffer
        channel_number = 2  # Acquisition on A and B
        ret, (boardhandle, memorySize_samples,
              bitsPerSample) = self._dll.GetChannelInfo(board)
        bytesPerSample = (bitsPerSample + 7) // 8
        bytesPerRecord = bytesPerSample * samplesPerRecord
        bytesPerBuffer = int(bytesPerRecord * recordsPerBuffer*channel_number)

        bufferCount = 4
        buffers = []
        for i in range(bufferCount):
            buffers.append(DMABuffer(bytesPerSample, bytesPerBuffer))
        # Set the record size
        self._dll.SetRecordSize(board, 0, samplesPerRecord)

        # Configure the number of records in the acquisition
        acquisition_timeout_sec = 10
        self._dll.SetRecordCount(board, recordsPerCapture)

        # Calculate the number of buffers in the acquisition
        buffersPerAcquisition = math.ceil(recordsPerCapture / recordsPerBuffer)

        self._dll.BeforeAsyncRead(board, 3,  # Channels A & B
                                  0,
                                  samplesPerRecord,
                                  int(recordsPerBuffer),
                                  recordsPerCapture,
                                  self._dll.ADMA_EXTERNAL_STARTCAPTURE |
                                  self._dll.ADMA_NPT)()

        # Post DMA buffers to board
        for buffer in buffers:
            self._dll.PostAsyncBuffer(board, buffer.addr, buffer.size_bytes)

        start = time.clock()  # Keep track of when acquisition started
        self._dll.StartCapture(board)  # Start the acquisition

        if time.clock() - start > acquisition_timeout_sec:
            self._dll.AbortCapture()
            raise Exception("Error: Capture timeout. Verify trigger")
            time.sleep(10e-3)

        # Preparation of the tables for the traces

        dataA = np.empty((recordsPerCapture, samplesPerRecord))
        dataB = np.empty((recordsPerCapture, samplesPerRecord))

        buffersCompleted = 0
        while buffersCompleted < buffersPerAcquisition:
            # Wait for the buffer at the head of the list of available
            # buffers to be filled by the board.
            buffer = buffers[buffersCompleted % len(buffers)]
            self._dll.WaitAsyncBufferComplete(board, buffer.addr, 500)

            data = np.reshape(buffer.buffer, (recordsPerBuffer*channel_number, -1))
            dataA[buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = data[:recordsPerBuffer]
            dataB[buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = data[recordsPerBuffer:]
            buffersCompleted += 1

            self._dll.PostAsyncBuffer(board, buffer.addr, buffer.size_bytes)

        self._dll.AbortAsyncRead(board)

        for buffer in buffers:
            buffer.__exit__()

        # Re-shaping of the data for demodulation and demodulation
        dataA = dataA[:,1:samplesPerTrace + 1]
        dataB = dataB[:,1:samplesPerTrace + 1]

        # Averaging if needed and converting binary numbers into Volts
        if average:
            dataA = np.mean(dataA, axis=0)
            dataB = np.mean(dataB, axis=0)

        dataA = (dataA-2**15)/65535*0.8+0.000459610322728
        dataB = (dataB-2**15)/65535*0.8+0.00154325074388

        return (dataA, dataB)


    def get_phase(self, startaftertrig, duration, recordsPerCapture,
                  recordsPerBuffer, freq, average, Ndemod, Npoints):

        board = self._dll.GetBoardBySystemID(1, 1)()

        # Number of samples per record: must be divisible by 32
        samplesPerSec = 1000000000.0
        samplesPerTrace = int(samplesPerSec * np.max(np.array(startaftertrig) + np.array(duration)))
        if samplesPerTrace % 32 == 0:
            samplesPerRecord = int(samplesPerTrace)
        else:
            samplesPerRecord = int((samplesPerTrace)/32 + 1)*32

        retCode = self._dll.GetChannelInfo(board)()
        bitsPerSample = self._dll.GetChannelInfo(board)[1]
        if retCode != self._dll.ApiSuccess:
            raise ValueError(cleandoc(self._dll.AlazarErrorToText(retCode)))

        # Compute the number of bytes per record and per buffer
        channel_number = 2  # Acquisition on A and B
        ret, (boardhandle, memorySize_samples,
              bitsPerSample) = self._dll.GetChannelInfo(board)
        bytesPerSample = (bitsPerSample + 7) // 8
        bytesPerRecord = bytesPerSample * samplesPerRecord
        bytesPerBuffer = int(bytesPerRecord * recordsPerBuffer*channel_number)

        # For converting data into volts
        channelRange = 0.4 # Volts
        bitsPerSample = 8
        code = (1 << (bitsPerSample - 1)) - 0.5

        bufferCount = int(round(recordsPerCapture / recordsPerBuffer))
        buffers = []
        for i in range(bufferCount):
            buffers.append(DMABuffer(bytesPerSample, bytesPerBuffer))

        # Set the record size
        self._dll.SetRecordSize(board, 0, samplesPerRecord)

        # Configure the number of records in the acquisition
#        acquisition_timeout_sec = 10
        self._dll.SetRecordCount(board, int(recordsPerCapture))

        # Calculate the number of buffers in the acquisition
        buffersPerAcquisition = round(recordsPerCapture / recordsPerBuffer)

        channelSelect = 3
        self._dll.BeforeAsyncRead(board, channelSelect,  # Channels A & B
                                  0,
                                  samplesPerRecord,
                                  int(recordsPerBuffer),
                                  int(recordsPerCapture),
                                  self._dll.ADMA_EXTERNAL_STARTCAPTURE |
                                  self._dll.ADMA_NPT)()

        # Post DMA buffers to board. ATTENTION it is very important not to do "for buffer in buffers"
        for i in range(bufferCount):
            buffer = buffers[i]
            self._dll.PostAsyncBuffer(board, buffer.addr, buffer.size_bytes)

        start = time.clock()  # Keep track of when acquisition started
        self._dll.StartCapture(board)  # Start the acquisition

        print 'Alazar waiting for trigger'
        # Preparation of the tables for the demodulation

        startSample = []
        samplesPerDemod = []
        samplesPerBlock = []
        NumberOfBlocks = []
        samplesMissing = []
        data = []
        dataExtended = []

        for i in range(2*Ndemod):
            startSample.append( int(samplesPerSec * startaftertrig[i%Ndemod]) )
            samplesPerDemod.append( int(samplesPerSec * duration[i%Ndemod]) )
            # Check wheter it is possible to cut each record in blocks of size equal
            # to an integer number of periods
            periodsPerBlock = 1
            while (periodsPerBlock * samplesPerSec < freq[i%Ndemod] * samplesPerDemod[i%Ndemod]
                   and periodsPerBlock * samplesPerSec % freq[i%Ndemod]):
                periodsPerBlock += 1
            samplesPerBlock.append( int(np.minimum(periodsPerBlock * samplesPerSec / freq[i%Ndemod],
                                                  samplesPerDemod[i%Ndemod])) )

            NumberOfBlocks.append( np.divide(samplesPerDemod[i%Ndemod], samplesPerBlock[i%Ndemod]) )
            samplesMissing.append( (-samplesPerDemod[i%Ndemod]) % samplesPerBlock[i%Ndemod] )
            # Makes the table that will contain the data
            data.append( np.empty((recordsPerCapture, samplesPerBlock[i%Ndemod])) )
            dataExtended.append( np.zeros((recordsPerBuffer, samplesPerDemod[i%Ndemod] + samplesMissing[i%Ndemod]),
                                          dtype='uint16') )

        start = time.clock()

        buffersCompleted = 0
        while buffersCompleted < buffersPerAcquisition:

            # Wait for the buffer at the head of the list of available
            # buffers to be filled by the board.
            buffer = buffers[buffersCompleted % len(buffers)]
            self._dll.WaitAsyncBufferComplete(board, buffer.addr, 10000)


            # Process data

            dataRaw = np.reshape(buffer.buffer, (recordsPerBuffer*channel_number, -1))

            for i in np.arange(Ndemod):
                dataExtended[i][:,:samplesPerDemod[i]] = dataRaw[:recordsPerBuffer,startSample[i]:startSample[i]+samplesPerDemod[i]]
                dataBlock = np.reshape(dataExtended[i],(recordsPerBuffer,-1,samplesPerBlock[i]))
                data[i][buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = np.sum(dataBlock, axis=1)

            for i in (np.arange(Ndemod) + Ndemod):
                dataExtended[i][:,:samplesPerDemod[i]] = dataRaw[(channel_number-1)*recordsPerBuffer:channel_number*recordsPerBuffer,startSample[i]:startSample[i]+samplesPerDemod[i]]
                dataBlock = np.reshape(dataExtended[i],(recordsPerBuffer,-1,samplesPerBlock[i]))
                data[i][buffersCompleted*recordsPerBuffer:(buffersCompleted+1)*recordsPerBuffer] = np.sum(dataBlock, axis=1)

            buffersCompleted += 1

            self._dll.PostAsyncBuffer(board, buffer.addr, buffer.size_bytes)

        self._dll.AbortAsyncRead(board)

        for i in range(bufferCount):
            buffer = buffers[i]
            buffer.__exit__()

        print time.clock() - start
#        if time.clock() - start > acquisition_timeout_sec:
#            raise Exception("Error: Capture timeout. Verify trigger")
#            time.sleep(10e-3)

        # Normalize the np.sum and convert data into Volts
        for i in range(2*Ndemod):
            normalisation = 1 if samplesMissing[i] else 0
            data[i][:,:samplesPerBlock[i]-samplesMissing[i]] /= NumberOfBlocks[i] + normalisation
            data[i][:,samplesPerBlock[i]-samplesMissing[i]:] /= NumberOfBlocks[i]
            data[i] = (data[i] / code - 1) * channelRange

        # calculate demodulation tables
        coses=[]
        sines=[]
        for i in range(Ndemod):
            dem = np.arange(samplesPerBlock[i])
            coses.append(np.cos(2. * math.pi * dem * freq[i] / samplesPerSec))
            sines.append(np.sin(2. * math.pi * dem * freq[i] / samplesPerSec))

        # prepare the structure of the answered array

        answerTypeDemod = []
        zerosDemod = 1 + int(np.floor(np.log10(Ndemod)))
        for i in range(Ndemod):
            answerTypeDemod += [('Phase' + str(i).zfill(zerosDemod), str(data[0].dtype)),
                                ('Magnitude' + str(i).zfill(zerosDemod), str(data[0].dtype))]
        
        if (average and Npoints == 0.0):
            answerDemod = np.zeros(1, dtype=answerTypeDemod)
        elif average:
            answerDemod = np.zeros((1, Npoints), dtype=answerTypeDemod)
        else:
            answerDemod = np.zeros((recordsPerCapture, 1), dtype=answerTypeDemod)

        # Demodulate the data, average them if asked and return the result

        for i in np.arange(Ndemod):
            Phasestring = 'Phase' + str(i).zfill(zerosDemod)
            Magstring = 'Magnitude' + str(i).zfill(zerosDemod)
            
            if average and Npoints == 0:
                data[i] = np.mean(data[i], axis=0)
                ansAI = 2 * np.mean((data[i]*coses[i]).reshape(1, -1), axis=1)
                ansAQ = 2 * np.mean((data[i]*sines[i]).reshape(1, -1), axis=1)
                ansBI = 2 * np.mean((data[i+Ndemod]*coses[i]).reshape(1, -1), axis=1)
                ansBQ = 2 * np.mean((data[i+Ndemod]*sines[i]).reshape(1, -1), axis=1)
                
                answerDemod[Phasestring][:1] = np.arctan2((ansAI*ansBQ-ansAQ*ansBI),(ansAI*ansBI+ansAQ*ansBQ))
                answerDemod[Magstring][:1] = np.sqrt(ansAI**2+ansAQ**2)
                
            elif average:
                data[i] = data[i].reshape(recordsPerCapture/Npoints,Npoints,samplesPerBlock[i])
                data[i] = np.mean(data[i], axis=0)
                ansAI = 2 * np.mean((data[i]*coses[i]).reshape(Npoints, -1), axis=1)
                ansAQ = 2 * np.mean((data[i]*sines[i]).reshape(Npoints, -1), axis=1)
                ansBI = 2 * np.mean((data[i+Ndemod]*coses[i]).reshape(Npoints, -1), axis=1)
                ansBQ = 2 * np.mean((data[i+Ndemod]*sines[i]).reshape(Npoints, -1), axis=1)               
                
                answerDemod[Phasestring][:1] = np.arctan2((ansAI*ansBQ-ansAQ*ansBI),(ansAI*ansBI+ansAQ*ansBQ))
                answerDemod[Magstring][:1] = np.sqrt(ansAI**2+ansAQ**2)
            else:
                ansAI = 2 * np.mean((data[i]*coses[i]).reshape(recordsPerCapture, 1, -1), axis=2)
                ansAQ = 2 * np.mean((data[i]*sines[i]).reshape(recordsPerCapture, 1, -1), axis=2)
                ansBI = 2 * np.mean((data[i+Ndemod]*coses[i]).reshape(recordsPerCapture, 1, -1), axis=2)
                ansBQ = 2 * np.mean((data[i+Ndemod]*sines[i]).reshape(recordsPerCapture, 1, -1), axis=2)
                
                answerDemod[Phasestring][:, :1] = np.arctan2((ansAI*ansBQ-ansAQ*ansBI),(ansAI*ansBI+ansAQ*ansBQ))
                answerDemod[Magstring][:, :1] = np.sqrt(ansAI**2+ansAQ**2)

        return answerDemod
        
DRIVERS = {'Alazar987x': Alazar987x}
