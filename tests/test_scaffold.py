from src.orion_sales_agent.specs import dashboard_spec, storyboard_spec


def test_dashboard_spec_has_widgets():
    spec = dashboard_spec()
    assert "widgets" in spec
    assert len(spec["widgets"]) >= 3


def test_storyboard_sections():
    spec = storyboard_spec(goal="Test")
    assert spec["goal"] == "Test"
    assert len(spec["sections"]) == 4
