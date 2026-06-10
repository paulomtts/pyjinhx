from pyjinhx.builtins import ConfirmDialog, PromptDialog


def test_confirm_dialog_markers_and_labels():
    html = str(ConfirmDialog(id="cd", confirm_label="Confirmar", cancel_label="Cancelar").render())
    assert 'data-px-dialog="confirm"' in html
    assert ">Confirmar<" in html and ">Cancelar<" in html
    assert 'aria-modal="true"' in html
    assert "px-confirm-dialog__message" in html


def test_confirm_dialog_contract():
    html = str(ConfirmDialog(id="cd", class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert "px-confirm-dialog mine" in html and 'data-k="v"' in html


def test_prompt_dialog_markers_and_labels():
    html = str(PromptDialog(id="pd", input_label="Nome", submit_label="OK!", cancel_label="Voltar").render())
    assert 'data-px-dialog="prompt"' in html
    assert ">Nome<" in html and ">OK!<" in html and ">Voltar<" in html
    assert 'method="dialog"' in html


def test_prompt_dialog_contract():
    html = str(PromptDialog(id="pd", class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert "px-prompt-dialog mine" in html and 'data-k="v"' in html
