import jca_core

import jca_pipeline


def test_pipeline_imports_with_core():
    assert jca_pipeline.__name__ == "jca_pipeline"
    assert jca_core.__name__ == "jca_core"
