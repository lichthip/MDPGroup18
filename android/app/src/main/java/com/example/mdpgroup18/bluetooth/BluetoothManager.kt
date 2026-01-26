package com.example.mdpgroup18.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.*

sealed class ConnectionStatus {
    object Disconnected : ConnectionStatus()
    data class Connecting(val deviceName: String) : ConnectionStatus()
    data class Connected(val deviceName: String) : ConnectionStatus()
    object Reconnecting : ConnectionStatus()
}

@SuppressLint("MissingPermission")
class BluetoothManager(private val context: Context) {

    companion object {
        private const val TAG = "BluetoothManager"
        private val MY_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        private const val RECONNECT_DELAY_MS = 3000L
    }

    private val bluetoothAdapter: BluetoothAdapter? = BluetoothAdapter.getDefaultAdapter()

    private val _connectionStatus = MutableStateFlow<ConnectionStatus>(ConnectionStatus.Disconnected)
    val connectionStatus = _connectionStatus.asStateFlow()

    private val incomingMessages = Channel<String>(Channel.UNLIMITED)
    private val outgoingMessages = Channel<String>(Channel.UNLIMITED)

    private var connectJob: Job? = null
    private var socketWrapper: BluetoothSocketWrapper? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    fun isSupported(): Boolean = bluetoothAdapter != null

    fun getPairedDevices(): List<BluetoothDevice> = bluetoothAdapter?.bondedDevices?.toList() ?: emptyList()

    fun connect(device: BluetoothDevice) {
        disconnect()
        connectJob = scope.launch {
            while (isActive) {
                try {
                    val name = device.name ?: "Unknown"
                    _connectionStatus.value = ConnectionStatus.Connecting(name)

                    val socket = device.createRfcommSocketToServiceRecord(MY_UUID)
                    bluetoothAdapter?.cancelDiscovery()
                    socket.connect()

                    socketWrapper = BluetoothSocketWrapper(socket)
                    _connectionStatus.value = ConnectionStatus.Connected(name)

                    startIO(socketWrapper!!)
                } catch (e: Exception) {
                    Log.e(TAG, "Connection failed/lost: ${e.message}")
                    _connectionStatus.value = ConnectionStatus.Reconnecting
                    socketWrapper?.close()
                    delay(RECONNECT_DELAY_MS)
                }
            }
        }
    }

    private suspend fun startIO(wrapper: BluetoothSocketWrapper) = coroutineScope {
        val input = wrapper.input
        val output = wrapper.output
        val buffer = ByteArray(1024)

        val readJob = launch {
            while (isActive) {
                try {
                    val bytesRead = input.read(buffer)
                    if (bytesRead > 0) {
                        val message = String(buffer, 0, bytesRead)
                        incomingMessages.send(message)
                    }
                } catch (e: IOException) { throw e }
            }
        }

        val writeJob = launch {
            for (msg in outgoingMessages) {
                try {
                    output.write(msg.toByteArray())
                    output.flush()
                } catch (e: IOException) { throw e }
            }
        }
        joinAll(readJob, writeJob)
    }

    fun send(message: String) {
        scope.launch { outgoingMessages.send(message) }
    }

    fun receive(): Channel<String> = incomingMessages

    fun disconnect() {
        connectJob?.cancel()
        socketWrapper?.close()
        socketWrapper = null
        _connectionStatus.value = ConnectionStatus.Disconnected
    }

    private class BluetoothSocketWrapper(private val socket: BluetoothSocket) {
        val input: InputStream = socket.inputStream
        val output: OutputStream = socket.outputStream
        fun close() { try { socket.close() } catch (e: IOException) { } }
    }
}