using Godot;

/// <summary>
/// Platformer controller for the Godot .NET build: acceleration, coyote time, jump buffer,
/// variable jump height. Input actions: move_left, move_right, jump.
/// </summary>
public partial class PlayerPlatformer : CharacterBody2D
{
	[Signal] public delegate void JumpedEventHandler();
	[Signal] public delegate void LandedEventHandler();

	[ExportGroup("Run")]
	[Export] public float MaxSpeed { get; set; } = 180f;
	[Export] public float Acceleration { get; set; } = 1400f;
	[Export] public float Friction { get; set; } = 1800f;

	[ExportGroup("Jump")]
	[Export] public float JumpHeight { get; set; } = 56f;
	[Export] public float TimeToApex { get; set; } = 0.38f;
	[Export] public float FallGravityMultiplier { get; set; } = 1.6f;
	[Export] public float JumpCutMultiplier { get; set; } = 0.45f;
	[Export] public float CoyoteTime { get; set; } = 0.1f;
	[Export] public float JumpBufferTime { get; set; } = 0.1f;
	[Export] public float TerminalVelocity { get; set; } = 600f;

	private float _gravity;
	private float _jumpVelocity;
	private float _coyoteTimer;
	private float _bufferTimer;
	private bool _wasOnFloor;

	public override void _Ready()
	{
		RecalculateJump();
	}

	public void RecalculateJump()
	{
		_gravity = 2f * JumpHeight / (TimeToApex * TimeToApex);
		_jumpVelocity = -2f * JumpHeight / TimeToApex;
	}

	public override void _PhysicsProcess(double delta)
	{
		float dt = (float)delta;
		Vector2 velocity = Velocity;

		if (!IsOnFloor())
		{
			float g = velocity.Y > 0f ? _gravity * FallGravityMultiplier : _gravity;
			velocity.Y = Mathf.Min(velocity.Y + g * dt, TerminalVelocity);
			_coyoteTimer -= dt;
		}
		else
		{
			_coyoteTimer = CoyoteTime;
		}

		_bufferTimer = Input.IsActionJustPressed("jump") ? JumpBufferTime : _bufferTimer - dt;
		if (_bufferTimer > 0f && _coyoteTimer > 0f)
		{
			velocity.Y = _jumpVelocity;
			_bufferTimer = 0f;
			_coyoteTimer = 0f;
			EmitSignal(SignalName.Jumped);
		}
		if (Input.IsActionJustReleased("jump") && velocity.Y < 0f)
		{
			velocity.Y *= JumpCutMultiplier;
		}

		float direction = Input.GetAxis("move_left", "move_right");
		velocity.X = Mathf.Abs(direction) > 0.01f
			? Mathf.MoveToward(velocity.X, direction * MaxSpeed, Acceleration * dt)
			: Mathf.MoveToward(velocity.X, 0f, Friction * dt);

		Velocity = velocity;
		MoveAndSlide();

		bool onFloor = IsOnFloor();
		if (onFloor && !_wasOnFloor)
		{
			EmitSignal(SignalName.Landed);
		}
		_wasOnFloor = onFloor;
	}
}
