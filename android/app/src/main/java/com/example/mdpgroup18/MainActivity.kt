package com.example.mdpgroup18

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.lifecycle.lifecycleScope
import com.example.mdpgroup18.bluetooth.BluetoothManager
import com.example.mdpgroup18.bluetooth.ConnectionStatus
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var bluetoothManager: BluetoothManager
    private lateinit var statusTextView: TextView
    private lateinit var robotStatusTextView: TextView
    private lateinit var robotPosTextView: TextView
    private lateinit var incomingMessagesTextView: TextView
    private lateinit var gridMapView: GridMapView
    private lateinit var messageInput: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // UI Component Binding
        statusTextView = findViewById(R.id.statusTextView)
        robotStatusTextView = findViewById(R.id.robotStatusTextView)
        robotPosTextView = findViewById(R.id.robotPosTextView)
        incomingMessagesTextView = findViewById(R.id.incomingMessagesTextView)
        gridMapView = findViewById(R.id.gridMapView)
        messageInput = findViewById(R.id.messageInput)

        bluetoothManager = BluetoothManager(this)
        checkPermissions()

        // Sync local Drag-and-Drop Obstacles to Bluetooth (Requirement C.6)
        gridMapView.onCommandGenerated = { cmd ->
            bluetoothManager.send(cmd)
        }

        // 1. Observe Connection Status and Display Device Name (Point 1 Fix)
        lifecycleScope.launch {
            bluetoothManager.connectionStatus.collect { status ->
                statusTextView.text = when(status) {
                    is ConnectionStatus.Disconnected -> "Status: Disconnected"
                    is ConnectionStatus.Connecting -> "Status: Connecting to ${status.deviceName}..."
                    is ConnectionStatus.Connected -> "Status: Connected to ${status.deviceName}"
                    is ConnectionStatus.Reconnecting -> "Status: Connection Lost. Retrying..."
                }
            }
        }

        // 2. Continuous Listener for Incoming Robot Data (Point 4 Fix)
        lifecycleScope.launch {
            for (message in bluetoothManager.receive()) {
                runOnUiThread {
                    incomingMessagesTextView.append("Robot: $message\n")
                    parseProtocol(message)
                }
            }
        }

        setupControls()
        updateRobotDisplay() // Initial state
    }

    private fun setupControls() {
        // Movement Buttons - Corrected Mapping (Point 3 Fix)
        findViewById<Button>(R.id.btnForward).setOnClickListener { sendMove("f") }
        findViewById<Button>(R.id.btnReverse).setOnClickListener { sendMove("r") } // r for reverse
        findViewById<Button>(R.id.btnTL).setOnClickListener { sendMove("tl") }
        findViewById<Button>(R.id.btnTR).setOnClickListener { sendMove("tr") }
        findViewById<Button>(R.id.btnSL).setOnClickListener { sendMove("sl") }
        findViewById<Button>(R.id.btnSR).setOnClickListener { sendMove("sr") }

        // Mode/Operational Buttons
        findViewById<Button>(R.id.btnBeginExplore).setOnClickListener { bluetoothManager.send("beginExplore") }
        findViewById<Button>(R.id.btnSendArena).setOnClickListener { bluetoothManager.send("sendArena") }

        // Set Start Coordinate - 0-indexed (Point 1,1 for center of 3x3)
        findViewById<Button>(R.id.btnSetStart).setOnClickListener {
            val x = findViewById<EditText>(R.id.startX).text.toString().toIntOrNull() ?: 1
            val y = findViewById<EditText>(R.id.startY).text.toString().toIntOrNull() ?: 1

            bluetoothManager.send("coordinate ($x,$y)")
            gridMapView.updateRobot(x, y, "N")
            updateRobotDisplay()
        }

        // Manual Text Send (Point 3 Fix)
        findViewById<Button>(R.id.sendButton).setOnClickListener {
            val msg = messageInput.text.toString()
            if (msg.isNotEmpty()) {
                bluetoothManager.send(msg)
                incomingMessagesTextView.append("Me: $msg\n")
                messageInput.text.clear()
            }
        }

        findViewById<Button>(R.id.connectButton).setOnClickListener { showDevicePicker() }
    }

    private fun sendMove(cmd: String) {
        bluetoothManager.send(cmd)

        // Local simulation logic to make the Tablet UI responsive immediately
        var nx = gridMapView.robotX
        var ny = gridMapView.robotY
        var nd = gridMapView.robotDirection

        when(cmd) {
            "f" -> when(nd) { "N"->ny++; "S"->ny--; "E"->nx++; "W"->nx-- }
            "r" -> when(nd) { "N"->ny--; "S"->ny++; "E"->nx--; "W"->nx++ }
            "tl" -> nd = when(nd) { "N"->"W"; "W"->"S"; "S"->"E"; "E"->"N" else->"N" }
            "tr" -> nd = when(nd) { "N"->"E"; "E"->"S"; "S"->"W"; "W"->"N" else->"N" }
            "sl" -> when(nd) { "N"->nx--; "S"->nx++; "E"->ny++; "W"->ny-- }
            "sr" -> when(nd) { "N"->nx++; "S"->nx--; "E"->ny--; "W"->ny++ }
        }
        gridMapView.updateRobot(nx, ny, nd)
        updateRobotDisplay()
    }

    private fun updateRobotDisplay() {
        robotPosTextView.text = "Robot: (${gridMapView.robotX}, ${gridMapView.robotY}) Facing: ${gridMapView.robotDirection}"
    }

    private fun parseProtocol(msg: String) {
        try {
            val clean = msg.trim()

            // Handle JSON: Status or Grid Updates
            if (clean.startsWith("{")) {
                val json = JSONObject(clean)
                if (json.has("grid")) {
                    gridMapView.setGridData(json.getString("grid"))
                }
                if (json.has("status")) {
                    robotStatusTextView.text = "Status: ${json.getString("status")}"
                }
            }
            // Handle ROBOT position updates: ROBOT,x,y,dir
            else if (clean.startsWith("ROBOT", ignoreCase = true)) {
                val p = clean.split(",")
                gridMapView.updateRobot(p[1].toInt(), p[2].toInt(), p[3])
                updateRobotDisplay()
            }
            // Handle Image Recognition updates: TARGET,obsId,label,face
            else if (clean.startsWith("TARGET", ignoreCase = true)) {
                val p = clean.split(",")
                gridMapView.obstacles.find { it.id == p[1].toInt() }?.apply {
                    this.label = p[2]
                    this.face = p[3]
                }
                gridMapView.invalidate()
            }
        } catch (e: Exception) {
            // Parsing errors logged to the on-screen console
            incomingMessagesTextView.append("Err: ${e.message}\n")
        }
    }

    @SuppressLint("MissingPermission")
    private fun showDevicePicker() {
        val devices = bluetoothManager.getPairedDevices()
        if (devices.isEmpty()) {
            Toast.makeText(this, "No paired devices found", Toast.LENGTH_SHORT).show()
            return
        }
        val names = devices.map { it.name ?: "Unknown" }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle("Select Robot Device")
            .setItems(names) { _, i -> bluetoothManager.connect(devices[i]) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun checkPermissions() {
        val perms = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            perms.add(Manifest.permission.BLUETOOTH_SCAN)
            perms.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        ActivityCompat.requestPermissions(this, perms.toTypedArray(), 1)
    }
}