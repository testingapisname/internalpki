{
  "subject": {{ toJson .Subject }},
  "keyUsage": ["digitalSignature"],
  "extKeyUsage": ["codeSigning"],
  "basicConstraints": {
    "isCA": false
  }
}
