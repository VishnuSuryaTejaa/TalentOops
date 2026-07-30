import React, { useState, useRef } from 'react';
import './UploadZone.css';

export default function UploadZone({ onFileSelect, onError }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const inputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file) => {
    if (file.type !== "application/pdf") {
      if (onError) onError("Please upload a valid PDF file.");
      return;
    }
    setSelectedFile(file);
    if (onFileSelect) {
      onFileSelect(file);
    }
  };

  const onButtonClick = () => {
    inputRef.current.click();
  };

  return (
    <div 
      className={`upload-zone ${dragActive ? "drag-active" : ""} ${selectedFile ? "has-file" : ""}`}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      <input 
        ref={inputRef} 
        type="file" 
        accept="application/pdf" 
        onChange={handleChange} 
        style={{ display: "none" }} 
      />
      
      {!selectedFile ? (
        <div className="upload-prompt" onClick={onButtonClick}>
          <div className="upload-icon">📄</div>
          <h3>Upload Candidate Resume</h3>
          <p>Drag and drop a PDF file here, or click to browse</p>
        </div>
      ) : (
        <div className="upload-success">
          <div className="upload-icon success-icon">✅</div>
          <h3>{selectedFile.name}</h3>
          <p>{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
          <button className="btn-sec btn-sm" onClick={(e) => { e.stopPropagation(); setSelectedFile(null); onFileSelect(null); }}>
            Remove
          </button>
        </div>
      )}
    </div>
  );
}
