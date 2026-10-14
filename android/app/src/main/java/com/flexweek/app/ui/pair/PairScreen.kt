package com.flexweek.app.ui.pair

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

internal const val DESKTOP_PAIR_PATH = "Settings > This computer > Devices > Pair a phone"

@Composable
fun PairScreen(
    state: PairUiState,
    onShowCode: () -> Unit,
    onShowQr: () -> Unit,
    onCodeChange: (String) -> Unit,
    onPair: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Pair with your computer", style = MaterialTheme.typography.titleLarge)
        Text(
            "On your computer open $DESKTOP_PAIR_PATH. It shows a code.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 8.dp, bottom = 16.dp),
        )
        if (state.mode == PairInputMode.Qr) {
            Box(
                modifier =
                    Modifier
                        .size(220.dp)
                        .border(2.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(16.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "Point the camera at the QR on your computer",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(24.dp),
                )
            }
            Text(
                "Point the camera at the code. Both devices need the same Wi‑Fi this first time.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 12.dp),
            )
            TextButton(onClick = onShowCode, modifier = Modifier.padding(top = 8.dp).height(48.dp)) {
                Text("Type the code instead")
            }
        } else {
            Text(
                "The 8-digit code on your computer",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.fillMaxWidth(),
            )
            BasicTextField(
                value = state.code,
                onValueChange = onCodeChange,
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(top = 4.dp)
                        .height(48.dp)
                        .border(
                            width = if (state.problem != null) 2.dp else 1.dp,
                            color = if (state.problem != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.outline,
                            shape = RoundedCornerShape(8.dp),
                        )
                        .padding(horizontal = 12.dp)
                        .semantics { contentDescription = "Pairing code" },
                textStyle = MaterialTheme.typography.titleLarge.copy(textAlign = TextAlign.Center),
                singleLine = true,
            )
            state.problem?.let { problem ->
                Text(
                    problem,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                )
            }
            Row(Modifier.fillMaxWidth().padding(top = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.canScan) {
                    TextButton(onClick = onShowQr, modifier = Modifier.weight(1f).height(48.dp)) {
                        Text("Scan instead")
                    }
                }
                Button(onClick = onPair, enabled = !state.joining, modifier = Modifier.weight(1f).height(48.dp)) {
                    Text(if (state.joining) "Pairing…" else "Pair")
                }
            }
        }
        Text(
            "The phone joins the account that is already on your computer and keeps a full copy. " +
                "Nothing goes through the internet unless the two cannot see each other.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 24.dp),
        )
    }
}
