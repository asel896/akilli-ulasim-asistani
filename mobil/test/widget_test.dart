import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobil/main.dart';

void main() {
  testWidgets(
    'Başlangıç ve hedef alanları gösterilir',
    (WidgetTester tester) async {
      await tester.pumpWidget(const UlasimApp());

      expect(
        find.text('Akıllı Ulaşım Asistanı'),
        findsOneWidget,
      );
      expect(
        find.byType(TextFormField),
        findsNWidgets(2),
      );
      expect(
        find.widgetWithText(FilledButton, 'Rota bul'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'Boş alanlarla rota araması yapılmaz',
    (WidgetTester tester) async {
      await tester.pumpWidget(const UlasimApp());

      await tester.tap(
        find.widgetWithText(FilledButton, 'Rota bul'),
      );
      await tester.pump();

      expect(
        find.text('Başlangıç yerini yaz.'),
        findsOneWidget,
      );
      expect(
        find.text('Hedef yerini yaz.'),
        findsOneWidget,
      );
      expect(
        find.byType(LinearProgressIndicator),
        findsNothing,
      );
    },
  );
}