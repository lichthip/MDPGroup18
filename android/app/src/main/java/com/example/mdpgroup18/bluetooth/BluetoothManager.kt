package com.example.mdpgroup18.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.content.Context
import android.util.Log
import android.widget.Toast
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.*

@SuppressLint("MissingPermission")
class BluetoothManager(private val context: Context) {

    companion object {
        private const val TAG = "BluetoothManager"
        private val MY_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        private const val RECONNECT_DELAY_MS = 3000L // try reconnect every 3 sec
    }

    private val bluetoothAdapter: BluetoothAdapter? = BluetoothAdapter.getDefaultAdapter()

    /** Flow to track connected device */
    private val _connectedDevice = MutableStateFlow<BluetoothDevice?>(null)
    val connectedDevice = _connectedDevice.asStateFlow()

    /** Channel for strings */
    private val incomingMessages = Channel<String>(Channel.UNLIMITED)
    private val outgoingMessages = Channel<String>(Channel.UNLIMITED)

    private var connectJob: Job? = null
    private var ioJob: Job? = null

    private var socketWrapper: BluetoothSocketWrapper? = null

    init {
        if (bluetoothAdapter == null) {
            Toast.makeText(context, "Bluetooth not supported", Toast.LENGTH_LONG).show()
        }
    }

    fun getPairedDevices(): List<BluetoothDevice> {
        return bluetoothAdapter?.bondedDevices?.toList() ?: emptyList()
    }

    fun connect(device: BluetoothDevice) {
        disconnect() // cancel previous connections
        _connectedDevice.value = device

        connectJob = CoroutineScope(Dispatchers.IO).launch {
            while (isActive) {
                try {
                    Log.d(TAG, "Attempting connection to ${device.name}")
                    val socket = device.createRfcommSocketToServiceRecord(MY_UUID)
                    bluetoothAdapter?.cancelDiscovery()
                    socket.connect()

                    socketWrapper = BluetoothSocketWrapper(socket)
                    _connectedDevice.value = device
                    Toast.makeText(context, "Connected to ${device.name}", Toast.LENGTH_SHORT).show()
                    startIO(socketWrapper!!)
                    break
                } catch (e: IOException) {
                    Log.e(TAG, "Connection failed, retrying in 3s", e)
                    _connectedDevice.value = null
                    delay(RECONNECT_DELAY_MS)
                }
            }
        }
    }

    fun send(message: String) {
        CoroutineScope(Dispatchers.IO).launch {
            outgoingMessages.send(message)
        }
    }

    fun receive(): Channel<String> = incomingMessages

    fun disconnect() {
        connectJob?.cancel()
        ioJob?.cancel()
        socketWrapper?.close()
        socketWrapper = null
        _connectedDevice.value = null
    }

    /** Start io loop with connected device */
    private fun startIO(socketWrapper: BluetoothSocketWrapper) {
        ioJob = CoroutineScope(Dispatchers.IO).launch {
            val input = socketWrapper.input
            val output = socketWrapper.output
            val buffer = ByteArray(1024)

            val readJob = launch {
                while (isActive) {
                    try {
                        val bytesRead = input.read(buffer)
                        if (bytesRead > 0) {
                            val message = String(buffer, 0, bytesRead)
                            incomingMessages.send(message)
                        }
                    } catch (e: IOException) {
                        Log.e(TAG, "Disconnected from device", e)
                        _connectedDevice.value = null
                        connect(_connectedDevice.value!!) // auto-reconnect
                        break
                    }
                }
            }

            val writeJob = launch {
                for (msg in outgoingMessages) {
                    try {
                        output.write(msg.toByteArray())
                    } catch (e: IOException) {
                        Log.e(TAG, "Error sending message", e)
                        _connectedDevice.value = null
                        connect(_connectedDevice.value!!) // auto-reconnect
                        break
                    }
                }
            }

            readJob.join()
            writeJob.join()
        }
    }

    /** Wrapper to handle io streams */
    private class BluetoothSocketWrapper(socket: android.bluetooth.BluetoothSocket) {
        val input: InputStream = socket.inputStream
        val output: OutputStream = socket.outputStream
        private val socketRef = socket
        fun close() {
            try { socketRef.close() } catch (e: IOException) { e.printStackTrace() }
        }
    }
}
