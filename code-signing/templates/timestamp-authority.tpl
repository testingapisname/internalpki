{
  "subject": {{ toJson .Subject }},
  "keyUsage": ["digitalSignature"],
  "basicConstraints": {
    "isCA": false
  },
  "extensions": [
    {
      "id": "2.5.29.37",
      "critical": true,
      "value": "MAoGCCsGAQUFBwMI"
    }
  ]
}
