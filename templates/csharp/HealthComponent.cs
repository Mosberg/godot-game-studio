using Godot;

/// <summary>Reusable health node. Add as a child of any actor.</summary>
public partial class HealthComponent : Node
{
	[Signal] public delegate void HealthChangedEventHandler(int current, int maximum);
	[Signal] public delegate void DamagedEventHandler(int amount, Node source);
	[Signal] public delegate void DiedEventHandler();

	[Export] public int MaxHealth { get; set; } = 100;
	[Export] public double InvulnerableTime { get; set; } = 0.0;

	public int CurrentHealth { get; private set; }
	public bool IsDead { get; private set; }

	private ulong _invulnerableUntilMs;

	public override void _Ready()
	{
		CurrentHealth = MaxHealth;
		EmitSignal(SignalName.HealthChanged, CurrentHealth, MaxHealth);
	}

	public bool IsInvulnerable => Time.GetTicksMsec() < _invulnerableUntilMs;

	public void TakeDamage(int amount, Node source = null)
	{
		if (IsDead || amount <= 0 || IsInvulnerable)
		{
			return;
		}
		CurrentHealth = Mathf.Max(0, CurrentHealth - amount);
		if (InvulnerableTime > 0.0)
		{
			_invulnerableUntilMs = Time.GetTicksMsec() + (ulong)(InvulnerableTime * 1000.0);
		}
		EmitSignal(SignalName.Damaged, amount, source);
		EmitSignal(SignalName.HealthChanged, CurrentHealth, MaxHealth);
		if (CurrentHealth == 0)
		{
			IsDead = true;
			EmitSignal(SignalName.Died);
		}
	}

	public void Heal(int amount)
	{
		if (IsDead || amount <= 0)
		{
			return;
		}
		CurrentHealth = Mathf.Min(MaxHealth, CurrentHealth + amount);
		EmitSignal(SignalName.HealthChanged, CurrentHealth, MaxHealth);
	}
}
