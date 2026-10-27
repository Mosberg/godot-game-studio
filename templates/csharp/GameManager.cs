using Godot;

/// <summary>
/// Autoload singleton (Project Settings > Globals > Autoload, name "GameManager").
/// Access from C# with GameManager.Instance, from GDScript with GameManager.
/// </summary>
public partial class GameManager : Node
{
	[Signal] public delegate void ScoreChangedEventHandler(int score);
	[Signal] public delegate void GameOverEventHandler(bool won);

	public static GameManager Instance { get; private set; }

	public int Score { get; private set; }

	public override void _EnterTree()
	{
		Instance = this;
	}

	public override void _ExitTree()
	{
		if (Instance == this)
		{
			Instance = null;
		}
	}

	public void AddScore(int amount)
	{
		Score += amount;
		EmitSignal(SignalName.ScoreChanged, Score);
	}

	public void EndGame(bool won)
	{
		EmitSignal(SignalName.GameOver, won);
	}

	public void ResetRun()
	{
		Score = 0;
		EmitSignal(SignalName.ScoreChanged, Score);
	}
}
