from PySide6.QtWidgets import QMessageBox

from app.core.project_validation import validate_project


def confirm_export(parent, project: dict) -> bool:
    issues = validate_project(project)
    if not issues:
        return True

    errors = sum(issue["severity"] == "error" for issue in issues)
    message = QMessageBox(parent)
    message.setWindowTitle("Kontrola przed eksportem")
    message.setIcon(QMessageBox.Warning)
    message.setText(f"Kontrola wykryła {len(issues)} elementów wymagających uwagi.")
    message.setInformativeText(
        (f"W tym błędy: {errors}. " if errors else "")
        + "Możesz wrócić do edycji albo świadomie wyeksportować dokument mimo ostrzeżeń."
    )
    message.setDetailedText("\n".join(f"• {issue['message']}" for issue in issues))
    export_anyway = message.addButton("Eksportuj mimo to", QMessageBox.AcceptRole)
    message.addButton("Wróć do edycji", QMessageBox.RejectRole)
    message.exec()
    return message.clickedButton() is export_anyway
