from ..support_scripts.init_checks import check_if_pyagri_is_built

def test_pyagri_built():
    assert check_if_pyagri_is_built()