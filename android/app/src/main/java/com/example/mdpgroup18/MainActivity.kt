package com.example.mdpgroup18

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.lifecycle.lifecycleScope
import com.example.mdpgroup18.bluetooth.BluetoothManager
import com.example.mdpgroup18.bluetooth.ConnectionStatus
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var bluetoothManager: BluetoothManager
    private lateinit var statusTextView: TextView
    private lateinit var incomingMessagesTextView: TextView
    private lateinit var connectButton: Button
    private lateinit var testSendButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusTextView = findViewById(R.id.statusTextView)
        incomingMessagesTextView = findViewById(R.id.incomingMessagesTextView)
        connectButton = findViewById(R.id.connectButton)
        testSendButton = findViewById(R.id.testSendButton)

        bluetoothManager = BluetoothManager(this)

        checkPermissions()

        // Connection Status Flow
        lifecycleScope.launch {
            bluetoothManager.connectionStatus.collect { status ->
                statusTextView.text = when (status) {
                    is ConnectionStatus.Disconnected -> getString(R.string.status_disconnected)
                    is ConnectionStatus.Connecting -> getString(R.string.status_connecting, status.deviceName)
                    is ConnectionStatus.Connected -> getString(R.string.status_connected, status.deviceName)
                    is ConnectionStatus.Reconnecting -> getString(R.string.status_reconnecting)
                }
            }
        }

        // Incoming Messages Flow (C.1 & C.4)
        lifecycleScope.launch {
            val channel = bluetoothManager.receive()
            for (message in channel) {
                // Append the new message to the console view
                val currentText = incomingMessagesTextView.text.toString()
                val newText = "$currentText\nRobot: $message"
                incomingMessagesTextView.text = newText
            }
        }

        connectButton.setOnClickListener {
            showDevicePicker()
        }

        testSendButton.setOnClickListener {
            val msg = "Hello from Android!"
            bluetoothManager.send(msg)

            // Also show what we sent in our own log
            val currentText = incomingMessagesTextView.text.toString()
            incomingMessagesTextView.text = "$currentText\nMe: $msg"
        }
    }

    @SuppressLint("MissingPermission")
    private fun showDevicePicker() {
        val devices = bluetoothManager.getPairedDevices()
        if (devices.isEmpty()) {
            Toast.makeText(this, getString(R.string.toast_no_paired_devices), Toast.LENGTH_SHORT).show()
            return
        }

        val names = devices.map { it.name ?: "Unknown" }.toTypedArray()

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.dialog_select_device))
            .setItems(names) { _, which ->
                bluetoothManager.connect(devices[which])
            }
            .setNegativeButton(getString(R.string.dialog_cancel), null)
            .show()
    }

    private fun checkPermissions() {
        val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        val missing = permissions.filter { ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) ActivityCompat.requestPermissions(this, missing.toTypedArray(), 1)
    }
}