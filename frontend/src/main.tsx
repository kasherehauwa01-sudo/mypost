import React from 'react'; import {createRoot} from 'react-dom/client'; import {CssBaseline,ThemeProvider,createTheme} from '@mui/material'; import App from './App'; import './style.css';
const theme=createTheme({palette:{primary:{main:'#4355b9'},background:{default:'#f6f7fb'}},shape:{borderRadius:14},typography:{fontFamily:'Inter,Roboto,Arial,sans-serif'}});
createRoot(document.getElementById('root')!).render(<React.StrictMode><ThemeProvider theme={theme}><CssBaseline/><App/></ThemeProvider></React.StrictMode>);
