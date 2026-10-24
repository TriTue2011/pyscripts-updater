"""Kiểm các lớp an toàn: chỉ tải từ GitHub, token chỉ gửi tới GitHub, đích không thoát thư mục pyscript."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import pytest

from custom_components.pyscript_updater.const import CONF_GITHUB_TOKEN, CONF_MAX_BACKUPS
from custom_components.pyscript_updater.coordinator import PyscriptUpdateCoordinator
from custom_components.pyscript_updater.utils import is_allowed_url, safe_join


def _chay(coro):
    """Chạy coroutine trên vòng sự kiện riêng, không đụng vòng sự kiện hiện hành của pytest."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(tmp_path, **options) -> PyscriptUpdateCoordinator:
    """Dựng coordinator không cần HA thật: chỉ các trường mà phần được thử dùng tới."""
    coord = object.__new__(PyscriptUpdateCoordinator)
    coord.config_entry = SimpleNamespace(
        options={"pyscript_dir": str(tmp_path), **options}, data={}, entry_id="e1"
    )

    class _Hass:
        async def async_add_executor_job(self, fn, *args):
            return fn(*args)

    coord.hass = _Hass()
    coord.data = {}
    return coord


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/u/r/tree/main/scripts",
        "https://raw.githubusercontent.com/u/r/main/a.py",
        "https://api.github.com/repos/u/r/contents/x?ref=main",
    ],
)
def test_url_github_duoc_phep(url):
    assert is_allowed_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/u/r/blob/main/a.py",  # không https
        "https://evil.example/a.py",
        "https://github.com.evil.example/a.py",  # tên miền giả
        "https://evil.example/https://github.com/a.py",
        "file:///etc/passwd",
        "",
    ],
)
def test_url_ngoai_github_bi_chan(url):
    assert not is_allowed_url(url)


def test_manifest_bo_nguon_ngoai_github(tmp_path):
    manifest = tmp_path / "_sources.txt"
    manifest.write_text(
        "# ghi chú\n"
        "https://github.com/u/r/blob/main/a.py|a.py\n"
        "https://evil.example/b.py|b.py\n"
        "https://github.com/u/r/tree/main/scripts|./|recursive\n",
        encoding="utf-8",
    )
    entries = _coord(tmp_path)._read_manifest(str(manifest))
    assert [e.dest for e in entries] == ["a.py", "./"]
    assert entries[1].recursive is True


def test_token_chi_gui_toi_github(tmp_path):
    coord = _coord(tmp_path, **{CONF_GITHUB_TOKEN: "ghp_gia"})
    assert coord._auth_headers("https://raw.githubusercontent.com/u/r/main/a.py")["Authorization"] == "Bearer ghp_gia"
    assert "Authorization" not in coord._auth_headers("https://evil.example/a.py")


def test_safe_join_chan_thoat_thu_muc(tmp_path):
    assert safe_join(str(tmp_path), "sub/a.py").startswith(os.path.realpath(tmp_path))
    for xau in ("../x.py", "sub/../../x.py", "/etc/passwd"):
        with pytest.raises(ValueError):
            safe_join(str(tmp_path), xau)


def test_safe_join_chan_symlink_tro_ra_ngoai(tmp_path):
    ngoai = tmp_path.parent / (tmp_path.name + "_ngoai")
    ngoai.mkdir()
    (tmp_path / "lk").symlink_to(ngoai)
    with pytest.raises(ValueError):
        safe_join(str(tmp_path), "lk/x.py")


def test_loc_dich_khong_an_toan(tmp_path):
    targets = [{"rel_path": "ok.py"}, {"rel_path": "../hai.py"}, {"rel_path": "sub/ba.py"}]
    kept = PyscriptUpdateCoordinator._filter_safe_targets(str(tmp_path), targets)
    assert [t["rel_path"] for t in kept] == ["ok.py", "sub/ba.py"]


def test_cai_tep_ghi_dung_cho_va_sao_luu(tmp_path):
    coord = _coord(tmp_path, **{CONF_MAX_BACKUPS: 2})
    (tmp_path / "a.py").write_text("cu", encoding="utf-8")
    _chay(coord.async_install_file("a.py", b"moi", reload_after=False, backup=True))
    assert (tmp_path / "a.py").read_bytes() == b"moi"
    assert (tmp_path / "a.py.bak.1").read_bytes() == b"cu"


def test_cai_tep_thoat_thu_muc_bi_tu_choi(tmp_path):
    coord = _coord(tmp_path)
    with pytest.raises(PermissionError):
        _chay(coord.async_install_file("../thoat.py", b"x", reload_after=False, backup=False))
    assert not (tmp_path.parent / "thoat.py").exists()


def test_khoi_phuc_thoat_thu_muc_bi_tu_choi(tmp_path):
    coord = _coord(tmp_path)
    kq = _chay(coord.async_restore_file("../thoat.py", version=1))
    assert kq == {"translation_key": "system_error", "success": False}
