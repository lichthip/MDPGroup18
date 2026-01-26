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
    private lateinit var connectButton: Button
    private lateinit var testSendButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusTextView = findViewById(R.id.statusTextView)
        connectButton = findViewById(R.id.connectButton)
        testSendButton = findViewById(R.id.testSendButton)

        bluetoothManager = BluetoothManager(this)

        if (!bluetoothManager.isSupported()) {
            Toast.makeText(this, getString(R.string.toast_bluetooth_unsupported), Toast.LENGTH_LONG).show()
        }

        // Request permissions
        checkPermissions()

        // Handle connection status changes
        lifecycleScope.launch {
            bluetoothManager.connectionStatus.collect { status ->
                statusTextView.text = when (status) {
                    is ConnectionStatus.Disconnected ->
                        getString(R.string.status_disconnected)
                    is ConnectionStatus.Connecting ->
                        getString(R.string.status_connecting, status.deviceName)
                    is ConnectionStatus.Connected ->
                        getString(R.string.status_connected, status.deviceName)
                    is ConnectionStatus.Reconnecting ->
                        getString(R.string.status_reconnecting)
                }
            }
        }

        // Handle incoming data
        lifecycleScope.launch {
            val channel = bluetoothManager.receive()
            for (message in channel) {
                // Logic for handling incoming strings
            }
        }

        connectButton.setOnClickListener {
            showDevicePicker()
        }

        testSendButton.setOnClickListener {
            bluetoothManager.send("Hello")
        }
    }

    @SuppressLint("MissingPermission")
    private fun showDevicePicker() {
        val devices = bluetoothManager.getPairedDevices()
        if (devices.isEmpty()) {
            Toast.makeText(this, getString(R.string.toast_no_paired_devices), Toast.LENGTH_SHORT).show()
            return
        }

        // The lint error usually happens here because it.name requires permission
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
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }

        val missing = permissions.filter {
            ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 1)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (grantResults.isNotEmpty() && grantResults.any { it != PackageManager.PERMISSION_GRANTED }) {
            // Handle case where user denies permission
        }
    }
}