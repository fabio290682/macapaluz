import "dart:convert";

import "package:flutter/material.dart";
import "package:geolocator/geolocator.dart";
import "package:http/http.dart" as http;

void main() {
  runApp(const CidadaoApp());
}

class CidadaoApp extends StatelessWidget {
  const CidadaoApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: "CIPEMAC Cidadao",
      theme: ThemeData(colorSchemeSeed: const Color(0xFF176a3a), useMaterial3: true),
      home: const SolicitarOsPage(),
    );
  }
}

class SolicitarOsPage extends StatefulWidget {
  const SolicitarOsPage({super.key});

  @override
  State<SolicitarOsPage> createState() => _SolicitarOsPageState();
}

class _SolicitarOsPageState extends State<SolicitarOsPage> {
  static const String apiBase = String.fromEnvironment(
    "API_BASE",
    defaultValue: "http://127.0.0.1:8001",
  );

  final _formKey = GlobalKey<FormState>();
  final _nomeCtrl = TextEditingController();
  final _telCtrl = TextEditingController();
  final _endCtrl = TextEditingController();
  final _bairroCtrl = TextEditingController();
  final _descCtrl = TextEditingController();

  bool _sending = false;
  Position? _pos;
  String _status = "Informe o problema e envie.";
  String? _osNumero;

  @override
  void dispose() {
    _nomeCtrl.dispose();
    _telCtrl.dispose();
    _endCtrl.dispose();
    _bairroCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _capturarLocalizacao() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() => _status = "Ative o GPS para abrir a O.S. no local.");
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        setState(() => _status = "Permissao de localizacao negada.");
        return;
      }

      final pos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
      setState(() {
        _pos = pos;
        _status = "Localizacao capturada: ${pos.latitude.toStringAsFixed(6)}, ${pos.longitude.toStringAsFixed(6)}";
      });
    } catch (e) {
      setState(() => _status = "Falha ao capturar localizacao: $e");
    }
  }

  Future<void> _enviar() async {
    if (!_formKey.currentState!.validate()) return;
    if (_pos == null) {
      setState(() => _status = "Capture a localizacao para abrir O.S. no local.");
      return;
    }

    setState(() {
      _sending = true;
      _status = "Enviando solicitacao para o portal...";
      _osNumero = null;
    });

    final payload = <String, dynamic>{
      "nome": _nomeCtrl.text.trim(),
      "telefone": _telCtrl.text.trim(),
      "endereco": _endCtrl.text.trim(),
      "bairro": _bairroCtrl.text.trim(),
      "descricao": _descCtrl.text.trim(),
      "lat": _pos!.latitude,
      "lng": _pos!.longitude,
    };

    try {
      final uri = Uri.parse("$apiBase/app-cidadao/solicitacoes");
      final res = await http
          .post(
            uri,
            headers: {"Content-Type": "application/json"},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 25));

      final Map<String, dynamic> data = jsonDecode(res.body) as Map<String, dynamic>;
      if (res.statusCode >= 400) {
        setState(() => _status = "Erro ao abrir O.S.: ${data["message"] ?? data["error"] ?? res.statusCode}");
      } else {
        final os = (data["os"] as Map<String, dynamic>?) ?? const <String, dynamic>{};
        setState(() {
          _osNumero = (os["numero_os"] ?? "").toString();
          _status = "Solicitacao enviada com sucesso.";
        });
      }
    } catch (e) {
      setState(() => _status = "Falha de conexao com o portal: $e");
    } finally {
      setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("CIPEMAC Cidadao"),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextFormField(
                  controller: _nomeCtrl,
                  decoration: const InputDecoration(labelText: "Nome"),
                  validator: (v) => (v == null || v.trim().isEmpty) ? "Informe seu nome." : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _telCtrl,
                  decoration: const InputDecoration(labelText: "Telefone"),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _endCtrl,
                  decoration: const InputDecoration(labelText: "Endereco (opcional)"),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _bairroCtrl,
                  decoration: const InputDecoration(labelText: "Bairro (opcional)"),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _descCtrl,
                  decoration: const InputDecoration(labelText: "Descricao do problema"),
                  maxLines: 4,
                  validator: (v) => (v == null || v.trim().isEmpty) ? "Descreva o problema." : null,
                ),
                const SizedBox(height: 14),
                FilledButton.tonalIcon(
                  onPressed: _sending ? null : _capturarLocalizacao,
                  icon: const Icon(Icons.my_location),
                  label: Text(_pos == null ? "Capturar localizacao" : "Atualizar localizacao"),
                ),
                const SizedBox(height: 10),
                FilledButton.icon(
                  onPressed: _sending ? null : _enviar,
                  icon: _sending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.send),
                  label: Text(_sending ? "Enviando..." : "Enviar para portal e abrir O.S."),
                ),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_status),
                        if (_osNumero != null && _osNumero!.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text("O.S. aberta: $_osNumero", style: const TextStyle(fontWeight: FontWeight.w700)),
                        ],
                        const SizedBox(height: 8),
                        Text("API: $apiBase", style: const TextStyle(fontSize: 12, color: Colors.black54)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
