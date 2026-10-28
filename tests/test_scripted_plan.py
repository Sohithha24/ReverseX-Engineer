from reversex.contracts import PageSnapshot, VisibleElement
from reversex.run import scripted_decision


def test_offline_smoke_test_plan_is_explicitly_scripted():
    snapshot = PageSnapshot(
        snapshot_id=1, url='http://127.0.0.1:8001', title='TaskBoard',
        visible_text='TaskBoard Add task', elements=[
            VisibleElement(element_id='s1_e1', kind='input', label='Task name'),
            VisibleElement(element_id='s1_e2', kind='button', label='Add task'),
        ],
    )
    actions = [scripted_decision(snapshot, i).action.value for i in range(6)]
    assert actions == ['fill', 'click', 'fill', 'click', 'reload', 'stop']
    assert scripted_decision(snapshot, 0).value == ''
