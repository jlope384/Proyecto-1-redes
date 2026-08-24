from app.main import ensure_git_repo


def test_ensure_git_repo_initializes_a_repo(tmp_path):
    repo_path = tmp_path / "demo-repo"

    ensure_git_repo(repo_path)

    assert (repo_path / ".git").is_dir()


def test_ensure_git_repo_is_idempotent(tmp_path):
    repo_path = tmp_path / "demo-repo"
    ensure_git_repo(repo_path)

    ensure_git_repo(repo_path)

    assert (repo_path / ".git").is_dir()
