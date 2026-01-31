package com.example.mdpgroup18

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View

class GridMapView(context: Context, attrs: AttributeSet) : View(context, attrs) {
    private val numColumns = 20
    private val numRows = 20
    private var cellSize = 0f

    // 0-indexed center of the 3x3 robot
    // (1,1) means the robot body covers (0,0) to (2,2)
    var robotX = 1
    var robotY = 1
    var robotDirection = "N"

    data class Obstacle(var id: Int, var x: Int, var y: Int, var face: String = "NONE", var target: String? = null)
    val obstacles = mutableListOf<Obstacle>()
    private var selectedObs: Obstacle? = null

    private var gridData = IntArray(400) { 0 }

    private val gridPaint = Paint().apply { color = Color.BLACK; strokeWidth = 1f; style = Paint.Style.STROKE }
    private val obsPaint = Paint().apply { color = Color.BLACK; style = Paint.Style.FILL }
    private val robotPaint = Paint().apply { color = Color.RED; style = Paint.Style.FILL; alpha = 180 }
    private val headPaint = Paint().apply { color = Color.YELLOW; style = Paint.Style.FILL }
    private val textPaint = Paint().apply { color = Color.WHITE; textSize = 22f; textAlign = Paint.Align.CENTER }
    private val targetPaint = Paint().apply { color = Color.GREEN; textSize = 30f; textAlign = Paint.Align.CENTER; typeface = Typeface.DEFAULT_BOLD }
    private val facePaint = Paint().apply { color = Color.CYAN; strokeWidth = 8f }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        // Calculate cell size based on the smaller dimension to stay square
        cellSize = width.toFloat() / numColumns

        // 1. Draw Grid & Background Obstacles
        for (r in 0 until 20) { // Rows
            for (c in 0 until 20) { // Columns
                val left = c * cellSize
                val top = (19 - r) * cellSize
                val right = left + cellSize
                val bottom = top + cellSize

                // Draw background grid data (if any)
                if (gridData[r * 20 + c] == 1) {
                    canvas.drawRect(left, top, right, bottom, obsPaint)
                }
                canvas.drawRect(left, top, right, bottom, gridPaint)
            }
        }

        // 2. Draw Drag-and-Drop Obstacles (2x2)
        obstacles.forEach { obs ->
            val left = obs.x * cellSize
            val top = (19 - (obs.y + 1)) * cellSize
            val right = left + (cellSize * 2)
            val bottom = top + (cellSize * 2)

            canvas.drawRect(left, top, right, bottom, obsPaint)
            canvas.drawText(obs.target ?: obs.id.toString(), left + cellSize, top + cellSize + 10f, if (obs.target != null) targetPaint else textPaint)

            if (obs.face != "NONE") {
                when(obs.face) {
                    "N" -> canvas.drawLine(left, top, right, top, facePaint)
                    "S" -> canvas.drawLine(left, bottom, right, bottom, facePaint)
                    "E" -> canvas.drawLine(right, top, right, bottom, facePaint)
                    "W" -> canvas.drawLine(left, top, left, bottom, facePaint)
                }
            }
        }

        // 3. Draw 3x3 Robot
        // If center is (1,1), pixels are from (1-1)*size to (1+2)*size
        val robotLeft = (robotX - 1) * cellSize
        val robotTop = (19 - (robotY + 1)) * cellSize
        val robotRight = robotLeft + (cellSize * 3)
        val robotBottom = robotTop + (cellSize * 3)

        val rRect = RectF(robotLeft, robotTop, robotRight, robotBottom)
        canvas.drawRoundRect(rRect, 10f, 10f, robotPaint)

        // Robot "Head" (Center of the leading side)
        val cx = robotLeft + (cellSize * 1.5f)
        val cy = robotTop + (cellSize * 1.5f)
        val hx: Float; val hy: Float
        val offset = cellSize * 1.2f

        when(robotDirection) {
            "N" -> { hx = cx; hy = cy - offset }
            "S" -> { hx = cx; hy = cy + offset }
            "E" -> { hx = cx + offset; hy = cy }
            else -> { hx = cx - offset; hy = cy }
        }
        canvas.drawCircle(hx, hy, cellSize * 0.4f, headPaint)
    }

    // to handle double tapping
    private val gestureDetector = GestureDetector(
        context,
        object : GestureDetector.SimpleOnGestureListener() {
            override fun onDoubleTap(e: MotionEvent): Boolean {
                val direction = arrayOf("N", "E", "S", "W", "NONE")
                val c = (e.x / cellSize).toInt()
                val r = 19 - (e.y / cellSize).toInt()

                val obs = obstacles.find { c in it.x..it.x + 1 && r in it.y..it.y + 1 }
                if (obs != null) {
                    val current = direction.indexOf(obs.face)
                    obs.face = direction[(current+1)%5]
                    return true
                }
                return false
            }
        }
    )

    override fun onTouchEvent(event: MotionEvent): Boolean {
        val c = (event.x / cellSize).toInt()
        val r = 19 - (event.y / cellSize).toInt()

        // if double tap occurs
        gestureDetector.onTouchEvent(event)

        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                selectedObs = obstacles.find { c in it.x..it.x+1 && r in it.y..it.y+1 }
                if (selectedObs == null && c in 0..18 && r in 0..18) {
                    val newObs = Obstacle(obstacles.size + 1, c, r, (obstacles.size + 1).toString())
                    obstacles.add(newObs)
                    selectedObs = newObs
                }
            }
            MotionEvent.ACTION_MOVE -> {
                selectedObs?.let {
                    it.x = c.coerceIn(0, 18)
                    it.y = r.coerceIn(0, 18)
                    invalidate()
                }
            }
            MotionEvent.ACTION_UP -> {
                selectedObs?.let {
                    if (event.x < 0 || event.x > width || event.y < 0 || event.y > height) {
                        obstacles.remove(it)
                        obstacles.forEachIndexed { i,obs ->
                            obs.id = i+1
                        }
                        onCommandGenerated?.invoke("REMOVE,B${it.id}")
                    } else {
                        onCommandGenerated?.invoke("ADD,B${it.id},(${it.x},${it.y})")
                    }
                }
                selectedObs = null
                invalidate()
            }
        }
        return true
    }

    var onCommandGenerated: ((String) -> Unit)? = null

    fun setGridData(data: String) {
        for (i in 0 until minOf(data.length, 400)) gridData[i] = if (data[i] != '0') 1 else 0
        invalidate()
    }

    fun updateRobot(x: Int, y: Int, dir: String) {
        // For a 3x3 robot, center must be between 1 and 18
        this.robotX = x.coerceIn(1, 18)
        this.robotY = y.coerceIn(1, 18)
        this.robotDirection = dir
        invalidate()
    }
}